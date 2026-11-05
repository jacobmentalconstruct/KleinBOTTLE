"""KleinOS v0.1: one fixed Docker sandbox, no host command execution.

The host calls Docker with argv only. Commands and filesystem operations run
inside the named, restricted Linux container. No host-path fallback exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import shutil
import subprocess
from typing import Any


IMAGE = "kleinbottle-kleinos:0.1"
CONTAINER = "kleinos-pc1"
VOLUME = "kleinos-pc1-files"
WORKSPACE = "/workspace"
MAX_FILE_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_COMMAND_SECONDS = 20


class ComputerError(RuntimeError):
    """Docker is unavailable, the container is unsafe, or an operation failed."""


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False


# This script executes INSIDE the Docker container, never in host Python.
# Commands are passed as JSON and run by /bin/sh inside the container.
# Filesystem operations resolve paths inside /workspace and reject escapes.
_RUNNER = r'''
import base64
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

ROOT = Path("/workspace").resolve()
MAX_FILE = 262144
MAX_OUTPUT = 65536


def respond(data):
    sys.stdout.write(json.dumps(data, ensure_ascii=True, separators=(",", ":")))
    sys.stdout.flush()


def check_path(value, *, must_exist=False):
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Invalid workspace path")
    raw = Path(value)
    target = (raw if raw.is_absolute() else ROOT / raw).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError("Path is outside /workspace")
    if must_exist and not target.exists():
        raise FileNotFoundError("No such workspace path")
    return target


def run_command(request):
    command = request["command"]
    if not isinstance(command, str) or not command.strip() or len(command) > 8192:
        raise ValueError("Command must be 1..8192 characters")
    directory = check_path(request.get("cwd", "/workspace"), must_exist=True)
    if not directory.is_dir():
        raise NotADirectoryError("Working directory is not a folder")
    seconds = min(20.0, max(0.1, float(request.get("timeout", 8))))
    proc = subprocess.Popen(
        ["/bin/sh", "-lc", command], cwd=directory,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    sel = selectors.DefaultSelector()
    for name, pipe in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        os.set_blocking(pipe.fileno(), False)
        sel.register(pipe, selectors.EVENT_READ, data=name)
    end_at = time.monotonic() + seconds
    timed_out = False
    truncated = False
    try:
        while sel.get_map() or proc.poll() is None:
            if time.monotonic() >= end_at:
                timed_out = True
                break
            for key, _ in sel.select(timeout=min(0.1, max(0, end_at - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    sel.unregister(key.fileobj)
                    continue
                used = sum(len(v) for v in streams.values())
                remaining = MAX_OUTPUT - used
                streams[key.data].extend(chunk[:max(0, remaining)])
                if len(chunk) > remaining:
                    truncated = True
                    break
            if truncated:
                break
    finally:
        if timed_out or truncated or proc.poll() is None:
            # Kill the whole command group even if its initial shell exited.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=2)
        sel.close()
        proc.stdout.close()
        proc.stderr.close()
    return {
        "exit_code": 124 if timed_out else (125 if truncated else proc.returncode),
        "stdout": streams["stdout"].decode("utf-8", errors="replace"),
        "stderr": streams["stderr"].decode("utf-8", errors="replace"),
        "timed_out": timed_out,
        "truncated": truncated,
    }


def process(request):
    operation = request.get("op")
    if operation == "execute":
        return run_command(request)
    if operation == "list":
        path = check_path(request.get("path", "."), must_exist=True)
        if not path.is_dir():
            raise NotADirectoryError("Not a folder")
        children = sorted(
            (p for p in path.iterdir() if p.resolve().is_relative_to(ROOT)),
            key=lambda p: (not p.is_dir(), p.name.casefold()),
        )
        if len(children) > 1000:
            raise ValueError("Too many entries in folder (limit 1000)")
        return {"entries": [{
            "name": item.name,
            "path": str(item.relative_to(ROOT)),
            "is_dir": item.is_dir(),
            "size": item.stat().st_size if item.is_file() else None,
        } for item in children]}
    if operation == "read":
        path = check_path(request["path"], must_exist=True)
        if not path.is_file():
            raise ValueError("Not a regular file")
        with path.open("rb") as file:
            data = file.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError("File exceeds 256 KiB editor limit")
        return {"content": data.decode("utf-8")}
    if operation == "write":
        path = check_path(request["path"])
        if path == ROOT:
            raise ValueError("Cannot overwrite workspace")
        if path.exists() and not path.is_file():
            raise ValueError("Not a regular file")
        data = base64.b64decode(request["content_b64"], validate=True)
        if len(data) > MAX_FILE:
            raise ValueError("File exceeds 256 KiB editor limit")
        # Parent must exist. No implicit arbitrary directory creation.
        if not path.parent.is_dir():
            raise FileNotFoundError("Parent folder does not exist")
        with path.open("wb") as file:
            file.write(data)
        return {"written": len(data)}
    raise ValueError("Unknown sandbox operation")


try:
    request = json.loads(sys.stdin.read(400000))
    respond({"ok": True, "result": process(request)})
except (ValueError, OSError, KeyError, UnicodeError) as exc:
    respond({"ok": False, "error": str(exc)})
'''


class ComputerBackend:
    """API for a single, fixed KleinOS container.

    Public operations: start, status, execute, list_files, read_file,
    write_file, stop. All file content lives in a Docker named volume.
    """

    def __init__(self, *, docker_executable: str = "docker") -> None:
        # Do not allow caller/game JSON to select a different executable or
        # host command. This parameter exists only to mock tests.
        if docker_executable != "docker":
            raise ValueError("Only the fixed Docker CLI is supported")

    @staticmethod
    def _docker(*args: str, input_text: str | None = None, timeout: float = 12) -> subprocess.CompletedProcess[str]:
        if not shutil.which("docker"):
            raise ComputerError("Docker CLI not found. Install/start Docker Desktop.")
        try:
            return subprocess.run(
                ["docker", *args], input=input_text, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=timeout, check=False, shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ComputerError("Docker did not respond within the timeout") from exc
        except OSError as exc:
            raise ComputerError(f"Unable to contact Docker: {exc}") from exc

    def _inspect(self) -> dict[str, Any] | None:
        result = self._docker("inspect", CONTAINER)
        if result.returncode:
            if "No such object" in result.stderr or "No such container" in result.stderr:
                return None
            raise ComputerError(f"Docker inspect failed: {result.stderr.strip() or result.stdout.strip()}")
        try:
            data = json.loads(result.stdout)
            if not isinstance(data, list) or len(data) != 1:
                raise ValueError("Expected one container")
            return data[0]
        except (ValueError, KeyError, TypeError) as exc:
            raise ComputerError("Docker returned invalid container metadata") from exc

    @staticmethod
    def _check_isolation(data: dict[str, Any]) -> None:
        host = data.get("HostConfig") or {}
        config = data.get("Config") or {}
        mounts = data.get("Mounts") or []
        expected_volume = (len(mounts) == 1 and mounts[0].get("Type") == "volume"
                           and mounts[0].get("Name") == VOLUME
                           and mounts[0].get("Destination") == WORKSPACE and mounts[0].get("RW"))
        expected = (
            host.get("NetworkMode") == "none"
            and host.get("ReadonlyRootfs") is True
            and not host.get("Privileged", False)
            and "ALL" in [str(v).upper() for v in (host.get("CapDrop") or [])]
            and "no-new-privileges" in (host.get("SecurityOpt") or [])
            and 0 < int(host.get("PidsLimit") or 0) <= 64
            and 0 < int(host.get("Memory") or 0) <= 268435456
            and 0 < int(host.get("NanoCpus") or 0) <= 1000000000
            and (host.get("PidMode") or "") not in {"host"}
            and str(config.get("User", "")).lower() in {"player:player", "10001:10001", "player", "10001"}
            and config.get("Image") == IMAGE
            and expected_volume
            and "/tmp" in (host.get("Tmpfs") or {})
        )
        if not expected:
            raise ComputerError(
                "Existing container does not match KleinOS isolation settings. "
                "Stop here; inspect it manually rather than reusing it."
            )

    def status(self) -> dict[str, bool]:
        info = self._inspect()
        if info is None:
            return {"exists": False, "running": False}
        self._check_isolation(info)
        return {"exists": True, "running": bool(info.get("State", {}).get("Running"))}

    def start(self) -> None:
        info = self._inspect()
        if info is not None:
            self._check_isolation(info)
            if info.get("State", {}).get("Running"):
                return
            result = self._docker("start", CONTAINER, timeout=25)
        else:
            result = self._docker(
                "run", "-d", "--pull", "never", "--name", CONTAINER,
                "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--pids-limit", "64",
                "--memory", "256m", "--cpus", "1",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                "-v", f"{VOLUME}:{WORKSPACE}", IMAGE,
                timeout=30,
            )
        if result.returncode:
            raise ComputerError(f"Cannot start sandbox: {result.stderr.strip() or result.stdout.strip()}")
        if not self.status()["running"]:
            raise ComputerError("Sandbox start returned without a running container")

    def stop(self) -> None:
        info = self._inspect()
        if info is None:
            return
        self._check_isolation(info)
        if info.get("State", {}).get("Running"):
            result = self._docker("stop", "-t", "3", CONTAINER, timeout=12)
            if result.returncode:
                raise ComputerError(f"Cannot stop sandbox: {result.stderr.strip()}")

    def _request(self, payload: dict[str, Any], *, timeout: float = 12) -> dict[str, Any]:
        if not self.status()["running"]:
            raise ComputerError("KleinOS container is not running. Call start() first.")
        result = self._docker(
            "exec", "-i", CONTAINER, "python", "-c", _RUNNER,
            input_text=json.dumps(payload), timeout=timeout,
        )
        if result.returncode:
            raise ComputerError(f"Sandbox operation failed: {result.stderr.strip() or result.stdout[:200]}")
        try:
            response = json.loads(result.stdout)
            if response.get("ok") is True:
                return response["result"]
            raise ComputerError(str(response.get("error") or "Unknown sandbox error"))
        except (ValueError, TypeError, KeyError) as exc:
            raise ComputerError("Sandbox returned invalid response") from exc

    def execute(self, command: str, *, cwd: str = WORKSPACE,
                timeout: float = 8) -> CommandResult:
        if not isinstance(command, str) or not command.strip() or len(command) > 8192:
            raise ValueError("Command must be 1..8192 characters")
        if not 0.1 <= timeout <= MAX_COMMAND_SECONDS:
            raise ValueError(f"Timeout must be 0.1..{MAX_COMMAND_SECONDS} seconds")
        data = self._request(
            {"op": "execute", "command": command, "cwd": cwd, "timeout": timeout},
            timeout=timeout + 6,
        )
        return CommandResult(**data)

    def list_files(self, path: str = ".") -> list[dict[str, Any]]:
        return self._request({"op": "list", "path": path})["entries"]

    def read_file(self, path: str) -> str:
        return self._request({"op": "read", "path": path})["content"]

    def write_file(self, path: str, content: str) -> None:
        data = content.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Editor file exceeds 256 KiB")
        self._request({"op": "write", "path": path,
                       "content_b64": base64.b64encode(data).decode("ascii")})

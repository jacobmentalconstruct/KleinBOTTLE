"""KleinOS backend tests. Default suite does not need Docker.

Opt in to live container checks with KLEINOS_DOCKER_INTEGRATION=1.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.computer_backend import (
    ComputerBackend, ComputerError, CommandResult,
    CONTAINER, IMAGE, MAX_FILE_BYTES, _RUNNER,
)


class BackendUnitTests(unittest.TestCase):
    def setUp(self):
        self.backend = ComputerBackend()

    def test_fixed_backend_identity(self):
        with self.assertRaises(ValueError):
            ComputerBackend(docker_executable="sh")

    def test_docker_missing_has_clear_error(self):
        with patch("src.computer_backend.shutil.which", return_value=None):
            with self.assertRaisesRegex(ComputerError, "Docker CLI not found"):
                self.backend.status()

    def test_execute_never_runs_command_in_host_shell(self):
        response = {"ok": True, "result": {"exit_code": 0, "stdout": "hi\n", "stderr": "",
                                           "timed_out": False, "truncated": False}}
        fake = subprocess.CompletedProcess([], 0, json.dumps(response), "")
        with patch.object(self.backend, "status", return_value={"exists": True, "running": True}), \
             patch.object(self.backend, "_docker", return_value=fake) as docker:
            command = "echo safe; $(echo not-host)"
            result = self.backend.execute(command)
        self.assertEqual(result, CommandResult(0, "hi\n", ""))
        argv = docker.call_args.args
        self.assertEqual(argv[:5], ("exec", "-i", CONTAINER, "python", "-c"))
        payload = json.loads(docker.call_args.kwargs["input_text"])
        self.assertEqual(payload["command"], command)
        self.assertEqual(payload["cwd"], "/workspace")
        self.assertNotIn(command, argv)  # command supplied as JSON on stdin

    def test_execution_rejects_unbounded_request(self):
        for command in ("", "   ", "x" * 8193):
            with self.assertRaises(ValueError):
                self.backend.execute(command)
        for seconds in (0, 21):
            with self.assertRaises(ValueError):
                self.backend.execute("echo hi", timeout=seconds)

    def test_file_size_limit_before_docker(self):
        with self.assertRaises(ValueError):
            self.backend.write_file("oversize.txt", "A" * (MAX_FILE_BYTES + 1))

    def test_start_uses_only_fixed_restricted_container_args(self):
        fake = subprocess.CompletedProcess([], 0, "container-id\n", "")
        with patch.object(self.backend, "_inspect", return_value=None), \
             patch.object(self.backend, "status", return_value={"exists": True, "running": True}), \
             patch.object(self.backend, "_docker", return_value=fake) as docker:
            self.backend.start()
        argv = docker.call_args.args
        self.assertEqual(argv[0], "run")
        for flag in ("--network", "none", "--read-only", "--cap-drop", "ALL",
                     "--security-opt", "no-new-privileges", "--memory", "256m",
                     "--pids-limit", "64", "--tmpfs", "--pull", "never"):
            self.assertIn(flag, argv)
        self.assertIn("kleinos-pc1-files:/workspace", argv)
        self.assertNotIn("--privileged", argv)
        self.assertNotIn("--mount", argv)
        self.assertEqual(argv[-1], IMAGE)

    def test_commands_not_dispatched_if_container_is_stopped(self):
        with patch.object(self.backend, "status", return_value={"exists": True, "running": False}), \
             patch.object(self.backend, "_docker") as docker:
            with self.assertRaisesRegex(ComputerError, "not running"):
                self.backend.execute("echo hi")
            docker.assert_not_called()

    def test_insecure_existing_container_is_rejected(self):
        with self.assertRaisesRegex(ComputerError, "isolation settings"):
            self.backend._check_isolation({"HostConfig": {"Privileged": True}})

    def test_secure_container_settings_accepted(self):
        # Matches the Docker command used in Task 1.
        self.backend._check_isolation({
            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True,
                           "Privileged": False, "CapDrop": ["ALL"],
                           "SecurityOpt": ["no-new-privileges"], "PidsLimit": 64,
                           "Memory": 268435456, "NanoCpus": 1000000000,
                           "PidMode": "", "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=16m"}},
            "Config": {"Image": IMAGE, "User": "player:player"},
            "Mounts": [{"Type": "volume", "Name": "kleinos-pc1-files",
                        "Destination": "/workspace", "RW": True}],
        })


class ContainerRunnerFileTests(unittest.TestCase):
    """File-operation protocol checks with a temporary fake workspace.

    Does not run shell commands on the host; uses only the runner's file APIs.
    Real command execution is covered by optional live-Docker tests below.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "workspace"
        self.root.mkdir()
        self.runner = _RUNNER.replace(
            'ROOT = Path("/workspace").resolve()',
            f"ROOT = Path({str(self.root)!r}).resolve()",
        )

    def request(self, **payload):
        process = subprocess.run(
            [sys.executable, "-c", self.runner], input=json.dumps(payload),
            capture_output=True, text=True, timeout=6,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_write_read_list_and_folder(self):
        (self.root / "notes").mkdir()
        written = self.request(op="write", path="notes/hello.txt",
                               content_b64=base64.b64encode(b"Hello\n").decode())
        self.assertEqual(written["result"]["written"], 6)
        read = self.request(op="read", path="notes/hello.txt")
        self.assertEqual(read["result"]["content"], "Hello\n")
        listing = self.request(op="list", path="notes")
        self.assertEqual(listing["result"]["entries"][0]["name"], "hello.txt")

    def test_rejects_traversal_and_absolute_host_path(self):
        for path in ("../outside.txt", "/etc/passwd", "notes/../../outside"):
            result = self.request(op="read", path=path)
            self.assertFalse(result["ok"])
            self.assertIn("outside", result["error"].lower())

    def test_rejects_symlink_outside_workspace(self):
        outside = Path(self.tmp.name) / "private.txt"
        outside.write_text("must stay private", encoding="utf-8")
        try:
            (self.root / "link.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation requires permissions on this platform")
        read = self.request(op="read", path="link.txt")
        self.assertFalse(read["ok"])
        self.assertIn("outside", read["error"].lower())
        names = [entry["name"] for entry in self.request(op="list", path=".")["result"]["entries"]]
        self.assertNotIn("link.txt", names)

    def test_rejects_oversize_file(self):
        (self.root / "too-big.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
        result = self.request(op="read", path="too-big.txt")
        self.assertFalse(result["ok"])
        self.assertIn("limit", result["error"])


@unittest.skipUnless(os.environ.get("KLEINOS_DOCKER_INTEGRATION") == "1",
                     "Set KLEINOS_DOCKER_INTEGRATION=1 to test live Docker")
class LiveDockerTests(unittest.TestCase):
    def test_real_commands_and_files(self):
        backend = ComputerBackend()
        backend.start()
        result = backend.execute("pwd && python --version")
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIn("/workspace", result.stdout)
        file_path = "kleinos-backend-smoke.txt"
        backend.write_file(file_path, "KleinOS works\n")
        self.assertEqual(backend.read_file(file_path), "KleinOS works\n")
        self.assertIn(file_path, [e["name"] for e in backend.list_files()])
        with self.assertRaises(ComputerError):
            backend.read_file("../etc/passwd")
        result = backend.execute("python -c 'import time; time.sleep(5)'", timeout=0.5)
        self.assertTrue(result.timed_out, result)


if __name__ == "__main__":
    unittest.main()

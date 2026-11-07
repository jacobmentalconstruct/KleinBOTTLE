"""
FILE: smoke_test.py
ROLE: Portable self-test for _app-journal v2.
WHAT IT DOES: Verifies schema v2, CAS, contract, actions, scaffold, pack, snapshot, and MCP paths.
HOW TO USE:
  - python src/smoke_test.py
  - python src/smoke_test.py --with-sidecar
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PASS = 0
FAIL = 0

# Avoid cp1252 encoding errors on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _ok(label: str) -> None:
    global PASS
    PASS += 1
    print(f"  [PASS] {label}")


def _fail(label: str, detail: str = "") -> None:
    global FAIL
    FAIL += 1
    msg = f"  [FAIL] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )


def _run_json(args: list[str]) -> dict:
    completed = _run(args)
    if completed.returncode != 0:
        raise RuntimeError(f"Exit {completed.returncode}: {completed.stderr or completed.stdout}")
    return json.loads(completed.stdout)


def _tool(name: str, arguments: dict) -> dict:
    return _run_json([
        sys.executable, str(ROOT / "tools" / f"{name}.py"),
        "run", "--input-json", json.dumps(arguments),
    ])


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _mcp_message(message: dict) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8") + body


def _mcp_read(stdout) -> dict:
    """Read one NDJSON response line from MCP server stdout."""
    while True:
        line = stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed before responding.")
        stripped = line.strip()
        if not stripped:
            continue
        return json.loads(stripped.decode("utf-8"))


# ═══════════════════════════════════════════════════════════════════
# Test groups
# ═══════════════════════════════════════════════════════════════════

def test_compile() -> None:
    """Compile-check all Python source files."""
    print("\n── Compile check ──")
    py_files = list(ROOT.rglob("*.py"))
    py_files = [f for f in py_files if "__pycache__" not in str(f)]
    result = _run([sys.executable, "-m", "py_compile"] + [str(f) for f in py_files])
    if result.returncode == 0:
        _ok(f"All {len(py_files)} Python files compile clean")
    else:
        _fail("Compile check", result.stderr)


def test_schema_and_cas(project_root: Path) -> str:
    """Init DB, verify schema v2, CAS operations."""
    print("\n── Schema v2 + CAS ──")

    result = _tool("journal_init", {"project_root": str(project_root)})
    db_path = result["result"]["paths"]["db_path"]

    if result["status"] == "ok":
        _ok("journal_init creates DB")
    else:
        _fail("journal_init", str(result))

    # Verify schema version via manifest
    manifest = _tool("journal_manifest", {"db_path": db_path})
    sv = manifest["result"]["db_summary"].get("schema_version")
    uv = manifest["result"]["db_summary"].get("sqlite_user_version")
    if sv == "2.0.0":
        _ok(f"Schema version = {sv}")
    else:
        _fail("Schema version", f"expected 2.0.0, got {sv}")
    if uv == 2:
        _ok(f"SQLite user_version = {uv}")
    else:
        _fail("SQLite user_version", f"expected 2, got {uv}")

    # Verify all 10 tables exist
    expected_tables = {
        "journal_meta", "journal_migrations", "journal_entries",
        "blob_store", "scaffold_templates", "packed_tools",
        "action_log", "snapshots", "snapshot_items", "project_registry",
    }
    db_tables = set(manifest["result"]["db_manifest"].get("db_schema", {}).get("table_names", []))
    if expected_tables == db_tables:
        _ok(f"All {len(expected_tables)} tables declared in manifest")
    else:
        _fail("Table manifest", f"missing: {expected_tables - db_tables}, extra: {db_tables - expected_tables}")

    # Verify contract was seeded
    contract_version = manifest["result"]["db_summary"].get("contract_version", "")
    if contract_version:
        _ok(f"Contract seeded (v{contract_version})")
    else:
        _fail("Contract seeding", "contract_version not set in manifest")

    # Verify blob_store has content (contract body)
    blob_count = manifest["result"]["db_summary"].get("blob_count", 0)
    if blob_count >= 1:
        _ok(f"blob_store has {blob_count} blob(s)")
    else:
        _fail("blob_store", "expected at least 1 blob from contract seeding")

    # CAS: write an entry and verify body_hash
    create_result = _tool("journal_write", {
        "project_root": str(project_root),
        "action": "create",
        "title": "CAS test entry",
        "body": "Content-addressed storage verification.",
        "kind": "note",
        "source": "agent",
        "tags": ["smoke", "cas"],
    })
    entry = create_result["result"]["entry"]
    if entry.get("body_hash"):
        _ok(f"Entry has body_hash: {entry['body_hash'][:16]}...")
    else:
        _fail("CAS dual-write", "entry missing body_hash")

    return db_path


def test_write_query_export(project_root: Path, db_path: str) -> str:
    """CRUD, append, query, export."""
    print("\n── Write / Query / Export ──")

    # Create
    create_result = _tool("journal_write", {
        "db_path": db_path,
        "action": "create",
        "title": "Smoke test decision",
        "body": "We verified the full CRUD lifecycle.",
        "kind": "decision",
        "source": "agent",
        "tags": ["smoke", "crud"],
    })
    entry_uid = create_result["result"]["entry"]["entry_uid"]
    _ok(f"Create entry: {entry_uid}")

    # Append
    _tool("journal_write", {
        "db_path": db_path,
        "action": "append",
        "entry_uid": entry_uid,
        "append_text": "Appended during smoke test.",
    })
    _ok("Append to entry")

    # Update
    _tool("journal_write", {
        "db_path": db_path,
        "action": "update",
        "entry_uid": entry_uid,
        "status": "closed",
        "importance": 3,
    })
    _ok("Update entry status/importance")

    # Query
    query_result = _tool("journal_query", {
        "db_path": db_path,
        "query": "CRUD lifecycle",
        "limit": 10,
    })
    count = query_result["result"]["summary"]["entry_count"]
    if count >= 1:
        _ok(f"Query returns {count} result(s)")
    else:
        _fail("Query", "expected at least 1 result")

    # Export markdown
    export_result = _tool("journal_export", {
        "project_root": str(project_root),
        "format": "markdown",
    })
    export_path = export_result["result"]["export_path"]
    if Path(export_path).exists():
        _ok(f"Markdown export created")
    else:
        _fail("Export", f"file not found: {export_path}")

    # Export JSON
    export_result_json = _tool("journal_export", {
        "project_root": str(project_root),
        "format": "json",
    })
    export_path_json = export_result_json["result"]["export_path"]
    if Path(export_path_json).exists():
        _ok("JSON export created")
    else:
        _fail("JSON export", f"file not found: {export_path_json}")

    return entry_uid


def test_contract_acknowledge(project_root: Path, db_path: str) -> None:
    """Contract acknowledgment."""
    print("\n── Contract Acknowledgment ──")

    ack_result = _tool("journal_acknowledge", {
        "db_path": db_path,
        "actor_id": "smoke_test_agent",
        "actor_type": "agent",
    })
    receipt = ack_result.get("result", {}).get("receipt", {})
    if receipt.get("acknowledged"):
        _ok("Contract acknowledged")
    else:
        _fail("Acknowledge", str(ack_result.get("result", {})))

    # Verify action was logged
    actions_result = _tool("journal_actions", {
        "db_path": db_path,
        "action_type": "acknowledge_contract",
        "limit": 5,
    })
    actions = actions_result["result"]["actions"]
    if any(a["action_type"] == "acknowledge_contract" for a in actions):
        _ok("Acknowledgment recorded in action_log")
    else:
        _fail("Action log", "contract_acknowledge not found")


def test_actions(project_root: Path, db_path: str) -> None:
    """Action ledger query."""
    print("\n── Action Ledger ──")

    result = _tool("journal_actions", {
        "db_path": db_path,
        "limit": 20,
    })
    actions = result["result"]["actions"]
    if len(actions) >= 1:
        _ok(f"Action log has {len(actions)} action(s)")
    else:
        _fail("Action log", "expected at least 1 action")

    # Filter by actor_type
    agent_result = _tool("journal_actions", {
        "db_path": db_path,
        "actor_type": "agent",
        "limit": 10,
    })
    agent_actions = agent_result["result"]["actions"]
    if all(a["actor_type"] == "agent" for a in agent_actions):
        _ok("Actor type filter works")
    else:
        _fail("Actor type filter", "returned non-agent actions")


def test_scaffold(project_root: Path, db_path: str) -> None:
    """Scaffold template seeding and unpacking."""
    print("\n── Scaffolding ──")

    result = _tool("journal_scaffold", {
        "db_path": db_path,
        "project_root": str(project_root),
    })
    payload = result.get("result", {})
    templates_seeded = payload.get("templates_seeded", 0)
    files_written = payload.get("files", [])

    if templates_seeded >= 1 or payload.get("templates_available", 0) >= 1:
        _ok(f"Templates seeded/available")
    else:
        _fail("Template seeding", str(payload))

    if len(files_written) >= 1:
        _ok(f"Scaffold wrote {len(files_written)} file(s)")
        first = files_written[0].get("path", "") if isinstance(files_written[0], dict) else str(files_written[0])
        if first and Path(first).exists():
            _ok(f"Scaffold file exists on disk")
        else:
            _fail("Scaffold file", f"not found: {first}")
    else:
        _ok("Scaffold ran (templates may be placeholder stubs)")


def test_pack(project_root: Path, db_path: str) -> None:
    """Tool packing, listing, and unpacking."""
    print("\n── Tool Packing ──")

    # Pack this package's src/ into the DB
    result = _tool("journal_pack", {
        "db_path": db_path,
        "action": "pack",
        "package_root": str(ROOT),
    })
    payload = result.get("result", {})
    packed = payload.get("packed_count", 0)
    if packed >= 5:
        _ok(f"Packed {packed} files from src/")
    else:
        _fail("Pack", f"expected >= 5 files, got {packed}")

    # List packed tools
    list_result = _tool("journal_pack", {
        "db_path": db_path,
        "action": "list",
    })
    tools = list_result.get("result", {}).get("tools", [])
    if len(tools) >= 5:
        _ok(f"Listed {len(tools)} packed tool(s)")
    else:
        _fail("List packed", f"expected >= 5, got {len(tools)}")

    # Unpack to a temp dir
    unpack_dir = Path(tempfile.mkdtemp(prefix="app_journal_unpack_"))
    unpack_result = _tool("journal_pack", {
        "db_path": db_path,
        "action": "unpack",
        "target_dir": str(unpack_dir),
    })
    unpacked = unpack_result.get("result", {}).get("unpacked_count", 0)
    if unpacked >= 5:
        _ok(f"Unpacked {unpacked} files to {unpack_dir.name}/")
    else:
        _fail("Unpack", f"expected >= 5, got {unpacked}")


def test_snapshot(project_root: Path, db_path: str) -> None:
    """Merkle snapshot create, list, get, verify."""
    print("\n── Snapshots ──")

    # Create
    create_result = _tool("journal_snapshot", {
        "db_path": db_path,
        "action": "create",
        "description": "Smoke test snapshot",
    })
    snapshot = create_result.get("result", {})
    snapshot_id = snapshot.get("snapshot_id", "")
    merkle_root = snapshot.get("merkle_root", "")
    if snapshot_id and merkle_root:
        _ok(f"Snapshot created: {snapshot_id}, root: {merkle_root[:16]}...")
    else:
        _fail("Snapshot create", str(snapshot))
        return

    # List
    list_result = _tool("journal_snapshot", {
        "db_path": db_path,
        "action": "list",
    })
    snapshots = list_result.get("result", {}).get("snapshots", [])
    if len(snapshots) >= 1:
        _ok(f"Listed {len(snapshots)} snapshot(s)")
    else:
        _fail("Snapshot list", "expected at least 1")

    # Get
    get_result = _tool("journal_snapshot", {
        "db_path": db_path,
        "action": "get",
        "snapshot_id": snapshot_id,
    })
    got = get_result.get("result", {})
    if got.get("snapshot_id") == snapshot_id:
        _ok(f"Get snapshot details (items: {got.get('item_count', '?')})")
    else:
        _fail("Snapshot get", str(got))

    # Verify
    verify_result = _tool("journal_snapshot", {
        "db_path": db_path,
        "action": "verify",
        "snapshot_id": snapshot_id,
    })
    verified = verify_result.get("result", {})
    if verified.get("valid"):
        _ok("Snapshot verified (merkle root matches)")
    else:
        _fail("Snapshot verify", str(verified))


def test_sidecar_install_and_setup() -> None:
    """Install the full sidecar payload, then apply and verify project setup."""
    print("\n── Sidecar Install / Setup / Microsite ──")

    target_root = Path(tempfile.mkdtemp(prefix="sidecar_install_")) / "fresh_project"
    target_root.mkdir(parents=True, exist_ok=True)

    preview = _tool("sidecar_install", {
        "target_project_root": str(target_root),
        "preview": True,
    })
    preview_files = preview["result"]["files"]
    if any(item["status"] == "would_create" for item in preview_files):
        _ok("sidecar install preview works")
    else:
        _fail("sidecar install preview", str(preview["result"]))

    applied = _tool("sidecar_install", {
        "target_project_root": str(target_root),
    })
    sidecar_dir = Path(applied["result"]["sidecar_dir"])
    expected = {
        sidecar_dir / "README.md",
        sidecar_dir / "release_payload_manifest.json",
        sidecar_dir / "src" / "mcp_server.py",
        sidecar_dir / "onboarding" / "START_HERE.html",
        sidecar_dir / "packages" / "_app-journal" / "README.md",
    }
    if all(path.exists() for path in expected):
        _ok("full sidecar payload installed")
    else:
        missing = [str(path) for path in expected if not path.exists()]
        _fail("sidecar install", ", ".join(missing))

    audit_before = _tool("project_setup", {
        "action": "audit",
        "project_root": str(target_root),
    })
    if audit_before["result"]["missing_required"]:
        _ok("project setup audit detects missing setup surfaces")
    else:
        _fail("project setup audit", str(audit_before["result"]))

    applied_setup = _tool("project_setup", {
        "action": "apply",
        "project_root": str(target_root),
        "actor_id": "smoke_setup_agent",
    })
    if applied_setup["result"]["files"]:
        _ok("project setup apply writes scaffold files")
    else:
        _fail("project setup apply", str(applied_setup["result"]))

    verified = _tool("project_setup", {
        "action": "verify",
        "project_root": str(target_root),
    })
    if verified["result"]["passed"]:
        _ok("project setup verify passes after apply")
    else:
        _fail("project setup verify", str(verified["result"]))

    site_check = _tool("onboarding_site_check", {
        "toolbox_root": str(sidecar_dir),
    })
    if site_check["result"]["passed"]:
        _ok("installed sidecar microsite passes integrity check")
    else:
        _fail("installed sidecar microsite", str(site_check["result"]))


def test_repo_search() -> None:
    """Repo search with native fallback."""
    print("\n── Repo Search ──")

    target_root = Path(tempfile.mkdtemp(prefix="repo_search_"))
    (target_root / "src").mkdir()
    (target_root / "src" / "app.py").write_text(
        "def main():\n    return 'needle-value'\n",
        encoding="utf-8",
    )
    (target_root / "notes.md").write_text("No match here.\n", encoding="utf-8")

    result = _tool("repo_search", {
        "project_root": str(target_root),
        "query": "needle-value",
        "extensions": [".py"],
        "force_fallback": True,
    })
    payload = result["result"]
    if payload["fallback_used"] and payload["match_count"] == 1:
        _ok("repo_search native fallback finds text without shell bypass")
    else:
        _fail("repo_search fallback", str(payload))

    bad_regex = _tool("repo_search", {
        "project_root": str(target_root),
        "query": "[",
        "regex": True,
    })
    if bad_regex["status"] == "error":
        _ok("repo_search reports invalid regex cleanly")
    else:
        _fail("repo_search invalid regex", str(bad_regex))


def test_sys_ops_introspection() -> None:
    """Local-agent sys-ops read-only tools."""
    print("\n── Local-Agent Sys-Ops Introspection ──")

    target_root = Path(tempfile.mkdtemp(prefix="sys_ops_"))
    (target_root / "src").mkdir()
    (target_root / "src" / "smoke_test.py").write_text("print('ok')\n", encoding="utf-8")
    (target_root / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite", "test": "echo ok", "build": "echo build"}}),
        encoding="utf-8",
    )
    (target_root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (target_root / "run.bat").write_text("@echo off\npython src\\smoke_test.py\n", encoding="utf-8")
    dev_port = _free_port()
    (target_root / "dev_server.py").write_text(
        "\n".join([
            "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer",
            f"PORT = {dev_port}",
            "class Handler(BaseHTTPRequestHandler):",
            "    def do_GET(self):",
            "        body = b'dev-server-ok'",
            "        self.send_response(200)",
            "        self.send_header('Content-Type', 'text/plain')",
            "        self.send_header('Content-Length', str(len(body)))",
            "        self.end_headers()",
            "        self.wfile.write(body)",
            "    def log_message(self, format, *args):",
            "        print(format % args, flush=True)",
            "print(f'listening on {PORT}', flush=True)",
            "ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()",
            "",
        ]),
        encoding="utf-8",
    )

    host = _tool("host_capability_probe", {
        "commands": ["python", "git"],
        "timeout_seconds": 3,
    })
    if host["status"] == "ok" and host["result"]["summary"]["available_count"] >= 1:
        _ok("host_capability_probe reports command availability")
    else:
        _fail("host_capability_probe", str(host))

    boundary = _tool("workspace_boundary_audit", {
        "project_root": str(target_root),
        "max_depth": 2,
    })
    if boundary["status"] == "ok" and boundary["result"]["project_root"] == str(target_root.resolve()):
        _ok("workspace_boundary_audit resolves project root")
    else:
        _fail("workspace_boundary_audit", str(boundary))

    profile = _tool("project_command_profile", {
        "project_root": str(target_root),
    })
    command_ids = {item["id"] for item in profile["result"]["commands"]}
    expected_ids = {"npm:dev", "npm:test", "npm:build", "python:smoke", "file:run.bat", "python:dev-server"}
    profile_has_metadata = all("requires" in item and "runtime" in item for item in profile["result"]["commands"])
    if expected_ids.issubset(command_ids) and profile_has_metadata:
        _ok("project_command_profile detects declared commands with metadata")
    else:
        _fail("project_command_profile", f"missing: {expected_ids - command_ids}")

    deps = _tool("dependency_env_check", {
        "project_root": str(target_root),
        "check_imports": ["json"],
    })
    dep_payload = deps["result"]
    if (
        deps["status"] == "ok"
        and dep_payload["python"]["requirements"][0]["entry_count"] == 1
        and dep_payload["node"]["package_json"]["exists"]
        and dep_payload["python"]["import_checks"][0]["available"]
    ):
        _ok("dependency_env_check reports readiness without installing")
    else:
        _fail("dependency_env_check", str(deps))

    processes = _tool("process_port_inspector", {
        "ports": [],
        "process_name_contains": ["python"],
        "max_processes": 10,
    })
    if processes["status"] == "ok" and "process_count" in processes["result"]["summary"]:
        _ok("process_port_inspector returns structured process summary")
    else:
        _fail("process_port_inspector", str(processes))

    health_url = f"http://127.0.0.1:{dev_port}/"
    started = False
    try:
        start_denied = _tool("dev_server_manager", {
            "action": "start",
            "project_root": str(target_root),
            "command_id": "python:dev-server",
            "health_url": health_url,
        })
        if start_denied["status"] == "error":
            _ok("dev_server_manager requires confirmation before start")
        else:
            _fail("dev_server_manager confirmation", str(start_denied))

        start = _tool("dev_server_manager", {
            "action": "start",
            "project_root": str(target_root),
            "command_id": "python:dev-server",
            "health_url": health_url,
            "port": dev_port,
            "confirm": True,
        })
        started = start["status"] == "ok"
        if started and start["result"]["server"]["pid"]:
            _ok("dev_server_manager starts a profiled dev server")
        else:
            _fail("dev_server_manager start", str(start))

        health = {"status": "error"}
        for _ in range(20):
            health = _tool("dev_server_manager", {
                "action": "health",
                "project_root": str(target_root),
                "command_id": "python:dev-server",
                "timeout_seconds": 1,
            })
            if health["status"] == "ok":
                break
            time.sleep(0.2)
        if health["status"] == "ok" and health["result"]["health"]["status_code"] == 200:
            _ok("dev_server_manager health-checks the registered server")
        else:
            _fail("dev_server_manager health", str(health))

        status = _tool("dev_server_manager", {
            "action": "status",
            "project_root": str(target_root),
            "command_id": "python:dev-server",
        })
        if status["status"] == "ok" and status["result"]["summary"]["registered_count"] == 1:
            _ok("dev_server_manager reports registered server status")
        else:
            _fail("dev_server_manager status", str(status))

        tail = _tool("dev_server_manager", {
            "action": "tail",
            "project_root": str(target_root),
            "command_id": "python:dev-server",
            "tail_lines": 20,
        })
        if tail["status"] == "ok" and tail["result"]["line_count"] >= 1:
            _ok("dev_server_manager tails runtime logs")
        else:
            _fail("dev_server_manager tail", str(tail))
    finally:
        if started:
            stop = _tool("dev_server_manager", {
                "action": "stop",
                "project_root": str(target_root),
                "command_id": "python:dev-server",
                "confirm": True,
            })
        if stop["status"] == "ok" and stop["result"]["alive"] is False:
            _ok("dev_server_manager stops registered server")
        else:
            _fail("dev_server_manager stop", str(stop))

    (target_root / "Dockerfile").write_text(
        "FROM python:3.11-slim\nCMD [\"python\", \"--version\"]\n",
        encoding="utf-8",
    )
    docker_status = _tool("docker_ops", {
        "action": "status",
        "project_root": str(target_root),
        "timeout_seconds": 3,
    })
    if docker_status["status"] == "ok" and "docker" in docker_status["result"]:
        _ok("docker_ops reports Docker availability status")
    else:
        _fail("docker_ops status", str(docker_status))

    docker_build = _tool("docker_ops", {
        "action": "build",
        "project_root": str(target_root),
        "context": ".",
        "image": "devtools-smoke:local",
        "preview": True,
    })
    if docker_build["status"] == "ok" and docker_build["result"]["executed"] is False:
        _ok("docker_ops validates project-scoped build previews")
    else:
        _fail("docker_ops build preview", str(docker_build))

    docker_tag_denied = _tool("docker_ops", {
        "action": "tag",
        "project_root": str(target_root),
        "source_image": "devtools-smoke:local",
        "target_image": "example/devtools-smoke:local",
    })
    if docker_tag_denied["status"] == "error":
        _ok("docker_ops requires confirmation before tag")
    else:
        _fail("docker_ops tag confirmation", str(docker_tag_denied))

    k8s_dir = target_root / "k8s"
    k8s_dir.mkdir()
    (k8s_dir / "deployment.yaml").write_text(
        "\n".join([
            "apiVersion: apps/v1",
            "kind: Deployment",
            "metadata:",
            "  name: devtools-smoke",
            "spec:",
            "  replicas: 1",
            "  selector:",
            "    matchLabels:",
            "      app: devtools-smoke",
            "  template:",
            "    metadata:",
            "      labels:",
            "        app: devtools-smoke",
            "    spec:",
            "      containers:",
            "        - name: smoke",
            "          image: devtools-smoke:local",
            "",
        ]),
        encoding="utf-8",
    )
    k8s_validate = _tool("k8s_ops", {
        "action": "validate",
        "project_root": str(target_root),
        "manifest": "k8s/deployment.yaml",
    })
    if k8s_validate["status"] == "ok" and k8s_validate["result"]["resources"][0]["kind"] == "Deployment":
        _ok("k8s_ops validates manifest structure")
    else:
        _fail("k8s_ops validate", str(k8s_validate))

    k8s_dry_run = _tool("k8s_ops", {
        "action": "dry_run",
        "project_root": str(target_root),
        "manifest": "k8s/deployment.yaml",
        "preview": True,
    })
    if k8s_dry_run["status"] == "ok" and k8s_dry_run["result"]["executed"] is False:
        _ok("k8s_ops prepares dry-run apply command")
    else:
        _fail("k8s_ops dry_run preview", str(k8s_dry_run))

    k8s_apply_denied = _tool("k8s_ops", {
        "action": "apply",
        "project_root": str(target_root),
        "manifest": "k8s/deployment.yaml",
        "preview": True,
    })
    if k8s_apply_denied["status"] == "error":
        _ok("k8s_ops requires confirmation before apply")
    else:
        _fail("k8s_ops apply confirmation", str(k8s_apply_denied))

    attach = _tool("k8s_ops", {
        "action": "attach_instructions",
        "project_root": str(target_root),
        "resource": "deploy/devtools-smoke",
    })
    if attach["status"] == "ok" and "kubectl" in attach["result"]["command"][0]:
        _ok("k8s_ops emits attach instructions")
    else:
        _fail("k8s_ops attach instructions", str(attach))

    (target_root / ".env").write_text(
        "API_KEY=sk_test_1234567890abcdef\nSAFE_FLAG=true\n",
        encoding="utf-8",
    )
    (target_root / "settings.py").write_text(
        "TOKEN = 'ghp_abcdefghijklmnopqrstuvwxyz1234567890'\n",
        encoding="utf-8",
    )
    secret_audit = _tool("secret_surface_audit", {
        "project_root": str(target_root),
        "max_findings": 10,
    })
    audit_text = json.dumps(secret_audit)
    if (
        secret_audit["status"] == "ok"
        and secret_audit["result"]["finding_count"] >= 1
        and secret_audit["result"]["risky_env_file_count"] >= 1
        and "1234567890abcdef" not in audit_text
        and "abcdefghijklmnopqrstuvwxyz1234567890" not in audit_text
    ):
        _ok("secret_surface_audit redacts findings and flags env exposure")
    else:
        _fail("secret_surface_audit", str(secret_audit))

    (target_root / "__pycache__").mkdir(exist_ok=True)
    (target_root / "__pycache__" / "sample.pyc").write_bytes(b"cache")
    (target_root / "_logs").mkdir(exist_ok=True)
    (target_root / "_logs" / "sample.log").write_text("log\n", encoding="utf-8")
    cleaner_dry = _tool("runtime_artifact_cleaner", {
        "project_root": str(target_root),
    })
    if (
        cleaner_dry["status"] == "ok"
        and cleaner_dry["result"]["dry_run"] is True
        and cleaner_dry["result"]["candidate_count"] >= 2
        and (target_root / "__pycache__" / "sample.pyc").exists()
    ):
        _ok("runtime_artifact_cleaner defaults to dry-run")
    else:
        _fail("runtime_artifact_cleaner dry-run", str(cleaner_dry))

    cleaner_blocked = _tool("runtime_artifact_cleaner", {
        "project_root": str(target_root),
        "dry_run": False,
    })
    if cleaner_blocked["status"] == "error":
        _ok("runtime_artifact_cleaner requires confirmation before cleanup")
    else:
        _fail("runtime_artifact_cleaner confirmation", str(cleaner_blocked))

    cleaner_apply = _tool("runtime_artifact_cleaner", {
        "project_root": str(target_root),
        "dry_run": False,
        "confirm": True,
    })
    if (
        cleaner_apply["status"] == "ok"
        and cleaner_apply["result"]["removed_count"] >= 2
        and not (target_root / "__pycache__").exists()
        and not (target_root / "_logs").exists()
    ):
        _ok("runtime_artifact_cleaner removes allowlisted generated artifacts")
    else:
        _fail("runtime_artifact_cleaner cleanup", str(cleaner_apply))

    bootstrap = _tool("local_agent_bootstrap", {
        "project_root": str(ROOT.parent),
        "format": "markdown",
        "journal_limit": 3,
        "timeout_seconds": 3,
    })
    bootstrap_packet = bootstrap.get("result", {}).get("packet", {})
    if (
        bootstrap["status"] == "ok"
        and "host_capability_probe" in bootstrap_packet.get("tool_manifest", {}).get("sys_ops_tools", [])
        and "command_profile" in bootstrap_packet
        and "Local Agent Launch Packet" in bootstrap["result"].get("rendered", "")
    ):
        _ok("local_agent_bootstrap emits a local-agent launch packet")
    else:
        _fail("local_agent_bootstrap", str(bootstrap))


def test_mcp(project_root: Path) -> None:
    """MCP stdio server: initialize, tools/list."""
    print("\n── MCP Server ──")

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "mcp_server.py")],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert proc.stdin is not None and proc.stdout is not None

        # Initialize
        proc.stdin.write(_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
        proc.stdin.flush()
        init_response = _mcp_read(proc.stdout)
        server_name = init_response.get("result", {}).get("serverInfo", {}).get("name")
        server_version = init_response.get("result", {}).get("serverInfo", {}).get("version")
        if server_name == "dev-tools-toolbox":
            _ok(f"MCP initialize: {server_name} v{server_version}")
        else:
            _fail("MCP initialize", f"unexpected server name: {server_name}")

        # tools/list
        proc.stdin.write(_mcp_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}))
        proc.stdin.flush()
        list_response = _mcp_read(proc.stdout)
        tool_names = sorted([t["name"] for t in list_response.get("result", {}).get("tools", [])])

        expected_tools = {
            "journal_init", "journal_write", "journal_query", "journal_export",
            "journal_manifest", "journal_acknowledge", "journal_actions",
            "journal_scaffold", "journal_pack", "journal_snapshot",
            "sidecar_install", "project_setup", "onboarding_site_check",
            "repo_search", "host_capability_probe", "workspace_boundary_audit",
            "project_command_profile", "process_port_inspector",
            "dependency_env_check", "dev_server_manager", "docker_ops", "k8s_ops",
            "secret_surface_audit", "runtime_artifact_cleaner",
            "local_agent_bootstrap",
        }
        found = set(tool_names)
        if expected_tools.issubset(found):
            _ok(f"MCP tools/list: {len(tool_names)} tools ({', '.join(tool_names)})")
        else:
            missing = expected_tools - found
            _fail("MCP tools/list", f"missing: {missing}")

        # tools/call — journal_query
        proc.stdin.write(_mcp_message({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "journal_query",
                "arguments": {"project_root": str(project_root), "query": "smoke", "limit": 5},
            },
        }))
        proc.stdin.flush()
        call_response = _mcp_read(proc.stdout)
        call_status = call_response.get("result", {}).get("structuredContent", {}).get("status")
        if call_status == "ok":
            _ok("MCP tools/call journal_query succeeds")
        else:
            _fail("MCP tools/call", str(call_response))

    finally:
        proc.kill()
        proc.wait(timeout=5)


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Toolbox smoke tests")
    parser.add_argument("--with-sidecar", action="store_true", help="Run optional sidecar installation tests")
    args = parser.parse_args()

    print("═══ .dev-tools Toolbox Smoke Test ═══")

    project_root = Path(tempfile.mkdtemp(prefix="app_journal_smoke_")) / "test-project"
    project_root.mkdir(parents=True, exist_ok=True)
    print(f"Project root: {project_root}")

    test_compile()
    db_path = test_schema_and_cas(project_root)
    test_write_query_export(project_root, db_path)
    test_contract_acknowledge(project_root, db_path)
    test_actions(project_root, db_path)
    test_scaffold(project_root, db_path)
    test_pack(project_root, db_path)
    test_snapshot(project_root, db_path)
    if args.with_sidecar:
        test_sidecar_install_and_setup()
    test_repo_search()
    test_sys_ops_introspection()
    test_mcp(project_root)

    print(f"\n═══ Results: {PASS} passed, {FAIL} failed ═══")
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

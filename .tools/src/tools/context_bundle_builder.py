"""
FILE: context_bundle_builder.py
ROLE: Phase C context bundle assembler for adversarial review.
WHAT IT DOES:
  - Runs project-mapper compile + exports tree and filedump markdown
  - Captures git diff (base_commit..HEAD or last commit) when available
  - Assembles a single bundle file the adversarial reviewer reads cold
  - Returns bundle path + manifest for use as context_bundle_path in STATUS.md
HOW TO USE:
  - python src/tools/context_bundle_builder.py metadata
  - python src/tools/context_bundle_builder.py run --input-json '{"project_root":"C:/path"}'
  - python src/tools/context_bundle_builder.py run --input-json '{"project_root":"C:/path","base_commit":"abc123","output_dir":"coordination/bundles"}'
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ensure_dir, now_stamp, standard_main, tool_error, tool_result


FILE_METADATA = {
    "tool_name": "context_bundle_builder",
    "version": "1.0.0",
    "entrypoint": "src/tools/context_bundle_builder.py",
    "category": "workflow",
    "summary": "Assemble a Phase C adversarial review bundle: project snapshot + diff.",
    "mcp_name": "context_bundle_builder",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "default": "."},
            "base_commit": {"type": "string", "default": ""},
            "output_dir": {"type": "string", "default": ""},
            "include_filedump": {"type": "boolean", "default": True},
            "diff_context_lines": {"type": "integer", "default": 8},
        },
        "additionalProperties": False,
    },
}

# projectmapper-cli venv path, relative to project_root/tools/
_PM_VENV_PYTHON = "project-mapper/.venv/Scripts/python.exe"
_PM_MODULE = "projectmapper.cli"


def _find_pm_python(project_root: Path) -> Path | None:
    candidate = project_root / "tools" / _PM_VENV_PYTHON
    if candidate.exists():
        return candidate
    return None


def _run_pm(pm_python: Path, project_root: Path, *args: str) -> tuple[bool, str]:
    """Run projectmapper CLI, return (success, output)."""
    cmd = [str(pm_python), "-m", _PM_MODULE, "--root", str(project_root)] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def _get_git_diff(project_root: Path, base_commit: str, context_lines: int) -> tuple[bool, str]:
    """Return (success, diff_text)."""
    if base_commit:
        ref = f"{base_commit}..HEAD"
    else:
        ref = "HEAD~1..HEAD"

    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "diff", f"--unified={context_lines}", ref],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout
        # Fall back: staged + unstaged
        result2 = subprocess.run(
            ["git", "-C", str(project_root), "diff", f"--unified={context_lines}"],
            capture_output=True, text=True, timeout=30,
        )
        if result2.stdout.strip():
            return True, result2.stdout
        return False, "(no diff output — clean working tree or not a git repo)"
    except FileNotFoundError:
        return False, "(git not found on PATH)"
    except Exception as exc:
        return False, str(exc)


def _get_git_log(project_root: Path, base_commit: str) -> str:
    ref = f"{base_commit}..HEAD" if base_commit else "-10"
    args = ["git", "-C", str(project_root), "log", "--oneline"]
    if base_commit:
        args.append(ref)
    else:
        args.extend(["-10"])
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "(git log unavailable)"
    except Exception:
        return "(git log unavailable)"


def _read_pm_export(project_root: Path, projection: str) -> str:
    """Read an existing projectmapper export file."""
    pm_dir = project_root / "_projectmapper"
    name = project_root.name
    suffixes = {
        "tree": f"{name}_project_tree.md",
        "filedump": f"{name}_project_filedump.md",
        "combined": f"{name}_project_tree_and_filedump.md",
    }
    path = pm_dir / suffixes.get(projection, "")
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return f"(export not found: {path})"


def run(arguments: dict) -> dict:
    project_root = Path(arguments.get("project_root", ".")).resolve()
    if not project_root.is_dir():
        return tool_error(FILE_METADATA["tool_name"], arguments, f"Not a directory: {project_root}")

    base_commit = str(arguments.get("base_commit", "")).strip()
    include_filedump = bool(arguments.get("include_filedump", True))
    diff_context = max(1, int(arguments.get("diff_context_lines", 8)))
    output_dir_arg = str(arguments.get("output_dir", "")).strip()

    output_dir = project_root / (output_dir_arg or "coordination/bundles")
    ensure_dir(output_dir)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_name = f"context_bundle_{stamp}.md"
    bundle_path = output_dir / bundle_name

    manifest: dict[str, Any] = {
        "generated_at": now_stamp(),
        "project_root": str(project_root),
        "base_commit": base_commit or "(none)",
        "bundle_path": str(bundle_path),
        "sections": [],
    }

    lines: list[str] = [
        "# Context Bundle for Adversarial Review",
        "",
        f"Generated: {now_stamp()}",
        f"Project root: `{project_root}`",
        f"Base commit: `{base_commit or 'none specified'}`",
        "",
        "> This bundle is a read-only snapshot. The reviewer starts cold — no prior context.",
        "> Review for bugs, frailties, stale assumptions, and missed improvements in tranche scope.",
        "",
        "---",
        "",
    ]

    # 1. Refresh projectmapper snapshot
    pm_python = _find_pm_python(project_root)
    if pm_python:
        ok, msg = _run_pm(pm_python, project_root, "--text", "compile")
        manifest["snapshot_compile"] = "succeeded" if ok else f"failed: {msg}"

        ok, _ = _run_pm(pm_python, project_root, "--text", "export", "tree")
        if ok:
            manifest["sections"].append("project_tree")
        ok2, _ = _run_pm(pm_python, project_root, "--text", "export", "filedump")
        if ok2 and include_filedump:
            manifest["sections"].append("filedump")
    else:
        manifest["snapshot_compile"] = "skipped — projectmapper not found"

    # 2. Project tree
    tree_md = _read_pm_export(project_root, "tree")
    lines += [
        "## Project Tree",
        "",
        tree_md,
        "",
        "---",
        "",
    ]

    # 3. File contents
    if include_filedump:
        filedump_md = _read_pm_export(project_root, "filedump")
        lines += [
            "## File Contents",
            "",
            filedump_md,
            "",
            "---",
            "",
        ]

    # 4. Commit log
    git_log = _get_git_log(project_root, base_commit)
    lines += [
        "## Commit Log",
        "",
        "```",
        git_log,
        "```",
        "",
        "---",
        "",
    ]

    # 5. Diff
    diff_ok, diff_text = _get_git_diff(project_root, base_commit, diff_context)
    manifest["sections"].append("diff")
    manifest["diff_available"] = diff_ok
    lines += [
        "## Diff",
        f"_{'Base: ' + base_commit if base_commit else 'Last commit vs working tree'}_",
        "",
        "```diff",
        diff_text,
        "```",
        "",
    ]

    bundle_path.write_text("\n".join(lines), encoding="utf-8")
    manifest["bundle_size_bytes"] = bundle_path.stat().st_size

    return tool_result(FILE_METADATA["tool_name"], arguments, {
        "bundle_path": str(bundle_path),
        "bundle_name": bundle_name,
        "manifest": manifest,
        "usage_hint": (
            f"Set context_bundle_path: {bundle_path} in STATUS.md YAML. "
            "Feed the bundle file to the adversarial reviewer with no other context."
        ),
    })


if __name__ == "__main__":
    raise SystemExit(standard_main(FILE_METADATA, run))

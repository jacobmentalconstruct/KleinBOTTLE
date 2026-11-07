"""Blocking call analysis — wraps stdlib scan_blocking_calls.

Responsibility: build a structured report dict. No rendering.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_STDLIB_TOOLS = Path(__file__).resolve().parents[2] / "stdlib" / "src" / "tools"
sys.path.insert(0, str(_STDLIB_TOOLS.parent))
sys.path.insert(0, str(_STDLIB_TOOLS))

import scan_blocking_calls


def build_report(target: str, *, extra_blocking: list[str] | None = None) -> dict:
    res = scan_blocking_calls.run({
        "root": target,
        "extra_blocking": extra_blocking or [],
    })

    report = {
        "mode": "blocking_calls",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(Path(target).resolve()),
        "parameters": {"extra_blocking": extra_blocking or []},
        "summary": {},
        "files": [],
        "errors": [],
    }

    if res.get("status") == "ok":
        d = res["result"]
        report["summary"] = d.get("summary", {})
        report["files"] = d.get("files", [])
    else:
        report["errors"].append({
            "source": "scan_blocking_calls",
            "error": res.get("result", {}).get("message", "unknown"),
        })

    return report

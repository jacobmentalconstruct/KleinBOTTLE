"""Dead code analysis — wraps stdlib dead_code_finder.

Responsibility: build a structured report dict. No rendering.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_STDLIB_TOOLS = Path(__file__).resolve().parents[2] / "stdlib" / "src" / "tools"
sys.path.insert(0, str(_STDLIB_TOOLS.parent))
sys.path.insert(0, str(_STDLIB_TOOLS))

import dead_code_finder


def build_report(target: str, *, include_imports: bool = True,
                 ignore_private: bool = True) -> dict:
    ignore_prefixes = ["_", "test_"] if ignore_private else []
    res = dead_code_finder.run({
        "project_root": target,
        "include_imports": include_imports,
        "ignore_prefixes": ignore_prefixes,
        "entry_points": ["main", "run", "app"],
    })

    report = {
        "mode": "dead_code",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(Path(target).resolve()),
        "parameters": {
            "include_imports": include_imports,
            "ignore_private": ignore_private,
        },
        "scan": {},
        "unused": [],
        "by_type": {},
        "errors": [],
    }

    if res.get("status") == "ok":
        d = res["result"]
        report["scan"] = {
            "files_scanned": d.get("files_scanned", 0),
            "definitions_found": d.get("definitions_found", 0),
            "unused_count": d.get("unused_count", 0),
        }
        report["unused"] = d.get("unused", [])
        report["by_type"] = d.get("by_type", {})
    else:
        report["errors"].append({
            "source": "dead_code_finder",
            "error": res.get("result", {}).get("message", "unknown"),
        })

    return report

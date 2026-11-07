"""Complexity analysis — wraps stdlib python_complexity_scorer.

Responsibility: build a structured report dict. No rendering.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_STDLIB_TOOLS = Path(__file__).resolve().parents[2] / "stdlib" / "src" / "tools"
sys.path.insert(0, str(_STDLIB_TOOLS.parent))
sys.path.insert(0, str(_STDLIB_TOOLS))

import python_complexity_scorer


def build_report(target: str, *, threshold: int = 8, top_n: int = 20) -> dict:
    res = python_complexity_scorer.run({
        "target": target,
        "threshold": threshold,
        "top_n": top_n,
        "include_all": False,
    })

    report = {
        "mode": "complexity",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(Path(target).resolve()),
        "parameters": {"threshold": threshold, "top_n": top_n},
        "scan": {},
        "flagged": [],
        "file_summary": [],
        "errors": [],
    }

    if res.get("status") == "ok":
        d = res["result"]
        report["scan"] = {
            "files_scanned": d.get("files_scanned", 0),
            "functions_found": d.get("functions_found", 0),
            "functions_above_threshold": d.get("functions_above_threshold", 0),
        }
        report["flagged"] = d.get("top_complex", [])
        report["file_summary"] = d.get("file_summary", [])
    else:
        report["errors"].append({
            "source": "python_complexity_scorer",
            "error": res.get("result", {}).get("message", "unknown"),
        })

    return report

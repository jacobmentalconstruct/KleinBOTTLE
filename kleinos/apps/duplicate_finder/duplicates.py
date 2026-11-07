"""Duplicate + similar code analysis — wraps stdlib duplicate_code_finder and similar_code_finder.

Responsibility: build a structured report dict. No rendering.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_STDLIB_TOOLS = Path(__file__).resolve().parents[2] / "stdlib" / "src" / "tools"
sys.path.insert(0, str(_STDLIB_TOOLS.parent))
sys.path.insert(0, str(_STDLIB_TOOLS))

import duplicate_code_finder
import similar_code_finder


def build_report(target: str, *, min_lines: int = 5,
                 similarity_threshold: float = 0.85, top_n: int = 20) -> dict:
    exact_res = duplicate_code_finder.run({
        "target": target, "min_lines": min_lines, "include_tests": True,
    })
    similar_res = similar_code_finder.run({
        "target": target, "method": "difflib", "threshold": similarity_threshold,
        "top_n": top_n, "min_lines": min_lines, "include_tests": True,
    })

    report = {
        "mode": "duplicates",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(Path(target).resolve()),
        "parameters": {
            "min_lines": min_lines,
            "similarity_threshold": similarity_threshold,
            "top_n": top_n,
        },
        "scan": {},
        "exact_duplicates": [],
        "structural_duplicates": [],
        "similar_pairs": [],
        "errors": [],
    }

    if exact_res.get("status") == "ok":
        d = exact_res["result"]
        report["scan"] = {
            "files_scanned": d.get("files_scanned", 0),
            "units_scanned": d.get("units_scanned", 0),
        }
        report["exact_duplicates"] = d.get("exact_clusters", [])
        report["structural_duplicates"] = d.get("structural_clusters", [])
        report["errors"].extend(d.get("read_errors", []))
    else:
        report["errors"].append({
            "source": "duplicate_code_finder",
            "error": exact_res.get("result", {}).get("message", "unknown"),
        })

    if similar_res.get("status") == "ok":
        d = similar_res["result"]
        report["similar_pairs"] = d.get("candidates", [])
        report["errors"].extend(d.get("read_errors", []))
    else:
        report["errors"].append({
            "source": "similar_code_finder",
            "error": similar_res.get("result", {}).get("message", "unknown"),
        })

    return report

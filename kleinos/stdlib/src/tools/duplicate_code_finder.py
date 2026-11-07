"""Find duplicate function/method implementations with AST fingerprints.

No writes, persistence, Git, embedding model, or external dependencies.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import standard_main, tool_error, tool_result
from lib.python_code_units import collect_python_units, public_unit

FILE_METADATA = {
    "tool_name": "duplicate_code_finder",
    "version": "1.0.0",
    "entrypoint": "src/tools/duplicate_code_finder.py",
    "category": "introspection",
    "summary": "Find exact and locally renamed structural duplicates among Python functions/methods.",
    "mcp_name": "duplicate_code_finder",
    "input_schema": {
        "type": "object", "required": ["target"],
        "properties": {
            "target": {"type": "string", "description": "Python project directory or .py file."},
            "min_lines": {"type": "integer", "default": 5},
            "include_tests": {"type": "boolean", "default": True},
            "extra_ignore": {"type": "array", "items": {"type": "string"}},
            "include_source": {"type": "boolean", "default": False},
        },
    },
}


def _groups(units: list[dict], fingerprint: str, *, structural_only: bool,
            include_source: bool) -> list[dict]:
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for unit in units:
        by_hash[unit[fingerprint] + "::" + ("async" if unit["kind"] in {"async_function", "async_method"} else "sync")].append(unit)
    clusters = []
    for key, members in sorted(by_hash.items()):
        if len(members) < 2:
            continue
        if structural_only and len({u["exact_fingerprint"] for u in members}) < 2:
            continue  # Exact duplicates are already listed separately.
        members = sorted(members, key=lambda u: (u["file"], u["line"]))
        clusters.append({
            "fingerprint": key.split("::")[0],
            "members": [public_unit(u, include_source=include_source) for u in members],
            "member_count": len(members),
        })
    clusters.sort(key=lambda c: (-c["member_count"], c["members"][0]["file"], c["members"][0]["line"]))
    return clusters


def run(arguments: dict) -> dict:
    name = FILE_METADATA["tool_name"]
    try:
        target = arguments.get("target", arguments.get("project_root"))
        if not target:
            raise ValueError("Provide 'target' (directory or .py file).")
        include_source = arguments.get("include_source", False)
        if type(include_source) is not bool:
            raise ValueError("include_source must be boolean")
        data = collect_python_units(target, min_lines=arguments.get("min_lines", 5),
                                    extra_ignore=arguments.get("extra_ignore", []),
                                    include_tests=arguments.get("include_tests", True))
        units = data["units"]
        exact = _groups(units, "exact_fingerprint", structural_only=False, include_source=include_source)
        structural = _groups(units, "structural_fingerprint", structural_only=True, include_source=include_source)
        return tool_result(name, arguments, {
            "files_scanned": data["files_scanned"],
            "units_scanned": len(units),
            "exact_clusters": exact, "structural_clusters": structural,
            "read_errors": data["errors"],
        })
    except (ValueError, OSError, TypeError) as exc:
        return tool_error(name, arguments, str(exc))


if __name__ == "__main__":
    standard_main(FILE_METADATA, run)

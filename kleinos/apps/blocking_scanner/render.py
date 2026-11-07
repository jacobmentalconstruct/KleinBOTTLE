"""Rendering for the blocking_scanner app.

Takes the report dict from scanner.py and returns a string. No I/O.
"""
from __future__ import annotations

import json
from pathlib import Path


def as_json(report: dict) -> str:
    return json.dumps(report, indent=2)


def write_output(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"Report written to: {out}")
    else:
        print(text)


def _rel(path: str, base: str) -> str:
    try:
        return str(Path(path).relative_to(base))
    except ValueError:
        return path


def render_markdown(report: dict) -> str:
    summary = report.get("summary", {})
    files = report.get("files", [])
    errors = report.get("errors", [])
    base = report.get("target", "")

    files_scanned = summary.get("files_scanned", "—")
    files_hit = summary.get("files_with_hits", 0)
    total_calls = summary.get("total_blocking_calls", 0)

    lines = [
        "# Blocking Call Scanner Report",
        "",
        f"**Target:** `{report['target']}`  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Files scanned:** {files_scanned}  ",
        f"**Files with blocking calls:** {files_hit}  ",
        f"**Total blocking calls found:** {total_calls}",
        "", "---", "",
    ]

    extra = report["parameters"].get("extra_blocking", [])
    if extra:
        lines += [f"**Extra patterns:** `{'`, `'.join(extra)}`", ""]

    if not files:
        lines += [
            "## Findings", "",
            "_No blocking calls found._", "",
            "> Blocking calls (subprocess, time.sleep, requests.*, socket.*, "
            "httpx.*, input, etc.) executed on a UI or async thread can freeze "
            "the application.",
            "",
        ]
    else:
        lines += [
            "## Findings", "",
            "Blocking calls that may freeze a UI or async thread if called on "
            "the main thread. Each is a manual review item — some may be intentional "
            "(CLI tools, worker threads, startup code).",
            "",
        ]
        for entry in sorted(files, key=lambda f: -f.get("hit_count", 0)):
            fname = _rel(entry["file"], base)
            hits = entry.get("hits", [])
            count = entry.get("hit_count", len(hits))
            lines += [f"### `{fname}` ({count} hit{'s' if count != 1 else ''})", ""]
            lines += [
                f"  - Line {h['line']}: `{h['call']}` _{h['kind']}_"
                for h in sorted(hits, key=lambda h: h["line"])
            ]
            lines.append("")

    if errors:
        lines += ["## Errors", ""]
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    return "\n".join(lines)

"""Rendering for all duplicate_finder modes: duplicates, dead_code, complexity.

Each renderer takes the report dict produced by its corresponding module and
returns a string (Markdown or JSON). No I/O here — callers decide where output goes.
"""
from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def as_json(report: dict) -> str:
    return json.dumps(report, indent=2)


def write_output(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"Report written to: {out}")
    else:
        print(text)


def _error_section(errors: list) -> list[str]:
    if not errors:
        return []
    lines = ["## Errors", ""]
    for e in errors:
        lines.append(f"- {e}")
    lines.append("")
    return lines


def _header(report: dict, title: str, extra_meta: list[str] | None = None) -> list[str]:
    scan = report.get("scan", {})
    lines = [
        f"# {title}",
        "",
        f"**Target:** `{report['target']}`  ",
        f"**Generated:** {report['generated_at']}  ",
    ]
    for item in (extra_meta or []):
        lines.append(item + "  ")
    lines += ["", "---", ""]
    return lines


# ---------------------------------------------------------------------------
# Duplicates renderer
# ---------------------------------------------------------------------------

def _fmt_member(m: dict) -> str:
    return f"  - `{m['qualified_name']}` ({m['file']}:{m['line']}, {m['line_count']} lines)"


def render_duplicates_markdown(report: dict) -> str:
    scan = report.get("scan", {})
    exact = report["exact_duplicates"]
    structural = report["structural_duplicates"]
    similar = report["similar_pairs"]
    p = report["parameters"]

    lines = _header(report, "Duplicate Finder Report", [
        f"**Files scanned:** {scan.get('files_scanned', '—')}",
        f"**Functions scanned:** {scan.get('units_scanned', '—')}",
        f"**Min lines:** {p['min_lines']} | "
        f"**Similarity threshold:** {p['similarity_threshold']} | "
        f"**Top N similar:** {p['top_n']}",
    ])

    lines += [
        "## Summary", "",
        "| Category | Count |", "|----------|-------|",
        f"| Exact duplicates (clusters) | {len(exact)} |",
        f"| Structural duplicates (clusters) | {len(structural)} |",
        f"| Similar pairs | {len(similar)} |",
        "",
    ]

    lines += ["## Exact Duplicates", ""]
    if not exact:
        lines += ["_None found._", ""]
    else:
        lines += ["Identical bodies (modulo whitespace). Safe deduplication candidates.", ""]
        for i, c in enumerate(exact, 1):
            lines += [f"### Cluster {i} ({c['member_count']} copies)", ""]
            lines.extend(_fmt_member(m) for m in c["members"])
            lines.append("")

    lines += ["## Structural Duplicates", ""]
    if not structural:
        lines += ["_None found._", ""]
    else:
        lines += ["Same structure, locally renamed variables.", ""]
        for i, c in enumerate(structural, 1):
            lines += [f"### Cluster {i} ({c['member_count']} copies)", ""]
            lines.extend(_fmt_member(m) for m in c["members"])
            lines.append("")

    lines += ["## Similar Pairs", ""]
    if not similar:
        lines += [f"_None found above {p['similarity_threshold']} threshold._", ""]
    else:
        lines += [
            f"Pairs scoring ≥ {p['similarity_threshold']}. "
            "Similarity is a signal, not proof of equivalent behavior.",
            "", "| Score | A | B |", "|-------|---|---|",
        ]
        for pair in similar:
            a, b = pair["a"], pair["b"]
            lines.append(
                f"| {pair['score']:.3f} "
                f"| `{a['qualified_name']}` ({a['file']}:{a['line']}) "
                f"| `{b['qualified_name']}` ({b['file']}:{b['line']}) |"
            )
        lines.append("")

    lines += _error_section(report.get("errors", []))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dead code renderer
# ---------------------------------------------------------------------------

def render_dead_code_markdown(report: dict) -> str:
    scan = report.get("scan", {})
    unused = report.get("unused", [])
    by_type = report.get("by_type", {})
    p = report["parameters"]

    lines = _header(report, "Dead Code Report", [
        f"**Files scanned:** {scan.get('files_scanned', '—')}",
        f"**Definitions found:** {scan.get('definitions_found', '—')}",
        f"**Unused:** {scan.get('unused_count', '—')}",
        f"**Include imports:** {p['include_imports']} | "
        f"**Ignore private (_, test_):** {p['ignore_private']}",
    ])

    # Type summary
    if by_type:
        lines += ["## Summary by Type", "", "| Type | Count |", "|------|-------|"]
        for kind, count in sorted(by_type.items()):
            lines.append(f"| {kind} | {count} |")
        lines.append("")

    # Unused items grouped by file
    if not unused:
        lines += ["## Unused Definitions", "", "_None found._", ""]
    else:
        lines += ["## Unused Definitions", ""]
        by_file: dict[str, list] = {}
        for item in unused:
            by_file.setdefault(item["file"], []).append(item)
        for fname, items in sorted(by_file.items()):
            lines += [f"### `{fname}`", ""]
            lines += [
                f"  - **{it['type']}** `{it['name']}` (line {it['line']})"
                for it in sorted(items, key=lambda x: x["line"])
            ]
            lines.append("")

    lines += _error_section(report.get("errors", []))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Complexity renderer
# ---------------------------------------------------------------------------

def render_complexity_markdown(report: dict) -> str:
    scan = report.get("scan", {})
    flagged = report.get("flagged", [])
    file_summary = report.get("file_summary", [])
    p = report["parameters"]
    above = scan.get("functions_above_threshold", 0)
    total = scan.get("functions_found", 0)

    lines = _header(report, "Complexity Report", [
        f"**Files scanned:** {scan.get('files_scanned', '—')}",
        f"**Functions found:** {total}",
        f"**Above threshold:** {above} ({round(above/total*100)}% of total)"
        if total else f"**Above threshold:** {above}",
        f"**Threshold:** {p['threshold']} | **Top N shown:** {p['top_n']}",
    ])

    if not flagged:
        lines += [
            f"## Flagged Functions (score ≥ {p['threshold']})", "",
            "_None found above threshold._", "",
        ]
    else:
        lines += [
            f"## Flagged Functions (score ≥ {p['threshold']})", "",
            "Sorted by composite score (cyclomatic complexity + nesting + length + params).", "",
            "| Score | Function | File | Line | Cyclomatic | Max Nesting | Lines | Params |",
            "|-------|----------|------|------|------------|-------------|-------|--------|",
        ]
        for f in flagged:
            lines.append(
                f"| {f['composite_score']} "
                f"| `{f['function']}` "
                f"| {f['file']} "
                f"| {f['line']} "
                f"| {f['cyclomatic_complexity']} "
                f"| {f['max_nesting_depth']} "
                f"| {f['line_count']} "
                f"| {f['param_count']} |"
            )
        lines.append("")

    if file_summary:
        lines += ["## Per-File Summary", "", "| File | Functions | Above Threshold |",
                  "|------|-----------|-----------------|"]
        for fs in sorted(file_summary, key=lambda x: -x.get("above_threshold", 0)):
            lines.append(
                f"| {fs.get('file', '?')} "
                f"| {fs.get('functions', '?')} "
                f"| {fs.get('above_threshold', '?')} |"
            )
        lines.append("")

    lines += _error_section(report.get("errors", []))
    return "\n".join(lines)

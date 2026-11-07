"""Rendering for concept_search. Takes a report dict, returns a string. No I/O."""
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


def render_markdown(report: dict) -> str:
    candidates = report.get("candidates", [])
    keywords = report.get("keywords", [])
    scan = report.get("scan", {})
    errors = report.get("errors", [])
    p = report["parameters"]
    search_mode = report.get("search_mode", "?")
    truncated = report.get("results_truncated", False)

    has_sem = any(c.get("semantic_score") is not None for c in candidates)
    has_kw = any(c.get("keyword_score") is not None for c in candidates)

    lines = [
        "# Concept Search Report",
        "",
        f"**Concept:** {report['concept']}  ",
        f"**Target:** `{report['target']}`  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Files scanned:** {scan.get('files_scanned', '—')} | "
        f"**Functions scanned:** {scan.get('units_scanned', '—')}  ",
        f"**Search mode:** {search_mode} | **Top N:** {p['top_n']}",
    ]

    if p.get("model"):
        lines.append(f"**Embedding model:** `{p['model']}`  ")

    lines += ["", "---", ""]

    if keywords:
        lines += [
            "**Keywords extracted:** " + ", ".join(f"`{k}`" for k in keywords),
            "",
        ]

    if not candidates:
        lines += [
            "## Candidates", "",
            "_No candidates found. Try a broader concept or lower --min-lines._",
            "",
        ]
    else:
        qualifier = " _(truncated)_" if truncated else ""
        lines += [
            f"## Candidates ({len(candidates)} shown{qualifier})", "",
            "> Scores are evidence signals, not proof of equivalent behaviour. "
            "Review candidates before using as donor material.",
            "",
        ]

        # Header adapts to what scores are present
        if has_sem and has_kw:
            lines += [
                "| Score | Sem | Kw | Function | File | Line | Lines |",
                "|-------|-----|----|----------|------|------|-------|",
            ]
            for c in candidates:
                sem = f"{c['semantic_score']:.3f}" if c.get("semantic_score") is not None else "—"
                kw = f"{c['keyword_score']:.3f}" if c.get("keyword_score") is not None else "—"
                lines.append(
                    f"| {c['score']:.3f} | {sem} | {kw} "
                    f"| `{c['qualified_name']}` | {c['file']} | {c['line']} | {c['line_count']} |"
                )
        else:
            score_label = "Sem score" if has_sem else "Score"
            lines += [
                f"| {score_label} | Function | File | Line | Lines |",
                f"|-----------|----------|------|------|-------|",
            ]
            for c in candidates:
                lines.append(
                    f"| {c['score']:.3f} "
                    f"| `{c['qualified_name']}` | {c['file']} | {c['line']} | {c['line_count']} |"
                )

        lines.append("")

    if errors:
        lines += ["## Errors", ""]
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    return "\n".join(lines)

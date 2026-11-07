"""Duplicate Finder — KleinOS app.

Scans a directory for duplicate and near-duplicate Python functions.
Renders a report and optionally exports it as Markdown or JSON.

Depends on kleinos/stdlib only. Not wired into the main KleinBOTTLE app.

Usage (standalone):
    python kleinos/apps/duplicate_finder/app.py <target_dir> [--export md|json] [--out <file>]
    python kleinos/apps/duplicate_finder/app.py --help
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# stdlib import — the only external dependency this app has
# ---------------------------------------------------------------------------
_STDLIB = Path(__file__).resolve().parents[2] / "stdlib" / "src"
sys.path.insert(0, str(_STDLIB))
sys.path.insert(0, str(_STDLIB / "tools"))

import duplicate_code_finder
import similar_code_finder


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _fmt_member(m: dict) -> str:
    return f"  - `{m['qualified_name']}` ({m['file']}:{m['line']}, {m['line_count']} lines)"


def build_report(target: str, min_lines: int = 5, similarity_threshold: float = 0.85,
                 top_n: int = 20) -> dict:
    exact_res = duplicate_code_finder.run({
        "target": target,
        "min_lines": min_lines,
        "include_tests": True,
    })
    similar_res = similar_code_finder.run({
        "target": target,
        "method": "difflib",
        "threshold": similarity_threshold,
        "top_n": top_n,
        "min_lines": min_lines,
        "include_tests": True,
    })

    report = {
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
        msg = exact_res.get("result", {}).get("message", "unknown")
        report["errors"].append({"source": "duplicate_code_finder", "error": msg})

    if similar_res.get("status") == "ok":
        d = similar_res["result"]
        report["similar_pairs"] = d.get("candidates", [])
        report["errors"].extend(d.get("read_errors", []))
    else:
        msg = similar_res.get("result", {}).get("message", "unknown")
        report["errors"].append({"source": "similar_code_finder", "error": msg})

    return report


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_markdown(report: dict) -> str:
    lines = []
    scan = report.get("scan", {})
    exact = report["exact_duplicates"]
    structural = report["structural_duplicates"]
    similar = report["similar_pairs"]
    params = report["parameters"]

    lines += [
        "# Duplicate Finder Report",
        "",
        f"**Target:** `{report['target']}`  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Files scanned:** {scan.get('files_scanned', '—')}  ",
        f"**Functions scanned:** {scan.get('units_scanned', '—')}  ",
        f"**Min lines:** {params['min_lines']} | "
        f"**Similarity threshold:** {params['similarity_threshold']} | "
        f"**Top N similar:** {params['top_n']}",
        "",
        "---",
        "",
    ]

    # Summary
    lines += [
        "## Summary",
        "",
        f"| Category | Count |",
        f"|----------|-------|",
        f"| Exact duplicates (clusters) | {len(exact)} |",
        f"| Structural duplicates (clusters) | {len(structural)} |",
        f"| Similar pairs | {len(similar)} |",
        "",
    ]

    # Exact duplicates
    lines += ["## Exact Duplicates", ""]
    if not exact:
        lines += ["_None found._", ""]
    else:
        lines += [
            f"These functions have identical bodies (modulo whitespace). "
            f"Safe candidates for deduplication.",
            "",
        ]
        for i, cluster in enumerate(exact, 1):
            lines += [
                f"### Cluster {i} ({cluster['member_count']} copies)",
                "",
            ]
            for m in cluster["members"]:
                lines.append(_fmt_member(m))
            lines.append("")

    # Structural duplicates
    lines += ["## Structural Duplicates", ""]
    if not structural:
        lines += ["_None found._", ""]
    else:
        lines += [
            "Same structure, locally renamed variables. Likely copy-paste with renaming.",
            "",
        ]
        for i, cluster in enumerate(structural, 1):
            lines += [
                f"### Cluster {i} ({cluster['member_count']} copies)",
                "",
            ]
            for m in cluster["members"]:
                lines.append(_fmt_member(m))
            lines.append("")

    # Similar pairs
    lines += ["## Similar Pairs", ""]
    if not similar:
        lines += ["_None found above threshold._", ""]
    else:
        lines += [
            f"Pairs scoring ≥ {report['parameters']['similarity_threshold']} "
            "by structural text similarity. Review manually — similarity is a signal, not proof.",
            "",
            "| Score | A | B |",
            "|-------|---|---|",
        ]
        for pair in similar:
            a = pair["a"]
            b = pair["b"]
            score = pair["score"]
            lines.append(
                f"| {score:.3f} | `{a['qualified_name']}` ({a['file']}:{a['line']}) "
                f"| `{b['qualified_name']}` ({b['file']}:{b['line']}) |"
            )
        lines.append("")

    # Errors
    if report.get("errors"):
        lines += ["## Errors", ""]
        for e in report["errors"]:
            lines.append(f"- {e}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scan a directory for duplicate and near-duplicate Python functions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("target", help="Directory or .py file to scan")
    p.add_argument("--min-lines", type=int, default=5, metavar="N",
                   help="Minimum function length to consider (default: 5)")
    p.add_argument("--threshold", type=float, default=0.85, metavar="F",
                   help="Similarity threshold 0-1 (default: 0.85)")
    p.add_argument("--top-n", type=int, default=20, metavar="N",
                   help="Max similar pairs to include (default: 20)")
    p.add_argument("--export", choices=["md", "json"], default="md",
                   help="Export format: md (default) or json")
    p.add_argument("--out", metavar="FILE",
                   help="Write report to FILE instead of stdout")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    report = build_report(
        target=args.target,
        min_lines=args.min_lines,
        similarity_threshold=args.threshold,
        top_n=args.top_n,
    )

    if args.export == "json":
        output = json.dumps(report, indent=2)
    else:
        output = render_markdown(report)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Report written to: {args.out}")
    else:
        print(output)

    # Non-zero exit if any scan errors
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

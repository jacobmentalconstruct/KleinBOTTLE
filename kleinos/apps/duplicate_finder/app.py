"""Duplicate Finder — KleinOS app entry point.

Three analysis modes, all pointing at a directory and exporting a report:

  duplicates   Exact and structurally-similar function duplicates
  dead-code    Unused functions, classes, and imports
  complexity   Cyclomatic complexity + nesting + length composite scores

Usage:
    python kleinos/apps/duplicate_finder/app.py <target> [--mode MODE] [--export md|json] [--out FILE]
    python kleinos/apps/duplicate_finder/app.py --help

Not wired into the main KleinBOTTLE app. Depends on kleinos/stdlib only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sibling modules importable when run as a script
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

import duplicates
import dead_code
import complexity
import render


# ---------------------------------------------------------------------------
# Mode dispatch
# ---------------------------------------------------------------------------

def _run_mode(mode: str, target: str, args: argparse.Namespace) -> dict:
    if mode == "duplicates":
        return duplicates.build_report(
            target,
            min_lines=args.min_lines,
            similarity_threshold=args.threshold,
            top_n=args.top_n,
        )
    if mode == "dead-code":
        return dead_code.build_report(
            target,
            include_imports=args.include_imports,
            ignore_private=not args.include_private,
        )
    if mode == "complexity":
        return complexity.build_report(
            target,
            threshold=args.complexity_threshold,
            top_n=args.top_n,
        )
    raise ValueError(f"Unknown mode: {mode!r}")


def _render(report: dict, fmt: str) -> str:
    if fmt == "json":
        return render.as_json(report)
    mode = report.get("mode")
    if mode == "duplicates":
        return render.render_duplicates_markdown(report)
    if mode == "dead_code":
        return render.render_dead_code_markdown(report)
    if mode == "complexity":
        return render.render_complexity_markdown(report)
    raise ValueError(f"No renderer for mode: {mode!r}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Code audit tool — scan a directory and export a report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Modes:\n"
            "  duplicates   Exact and structural function duplicates (default)\n"
            "  dead-code    Unused functions, classes, and imports\n"
            "  complexity   Cyclomatic complexity and nesting scores\n"
        ),
    )
    p.add_argument("target", help="Directory or .py file to scan")
    p.add_argument("--mode", choices=["duplicates", "dead-code", "complexity"],
                   default="duplicates", metavar="MODE",
                   help="Analysis mode: duplicates | dead-code | complexity (default: duplicates)")
    p.add_argument("--export", choices=["md", "json"], default="md",
                   help="Output format: md (default) or json")
    p.add_argument("--out", metavar="FILE",
                   help="Write report to FILE instead of stdout")

    # duplicates options
    p.add_argument("--min-lines", type=int, default=5, metavar="N",
                   help="[duplicates] Min function length to consider (default: 5)")
    p.add_argument("--threshold", type=float, default=0.85, metavar="F",
                   help="[duplicates] Similarity threshold 0–1 (default: 0.85)")
    p.add_argument("--top-n", type=int, default=20, metavar="N",
                   help="[duplicates|complexity] Max results to include (default: 20)")

    # dead-code options
    p.add_argument("--include-imports", action="store_true", default=True,
                   help="[dead-code] Include unused imports (default: on)")
    p.add_argument("--include-private", action="store_true", default=False,
                   help="[dead-code] Include private (_, test_) definitions (default: off)")

    # complexity options
    p.add_argument("--complexity-threshold", type=int, default=8, metavar="N",
                   help="[complexity] Composite score threshold (default: 8)")

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = _run_mode(args.mode, args.target, args)
    output = _render(report, args.export)
    render.write_output(output, args.out)
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())

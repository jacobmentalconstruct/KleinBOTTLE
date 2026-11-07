"""Concept Search — KleinOS app entry point.

Given a plain-language description of something you want to build, finds
existing Python functions in a directory that may serve as donor material.

Two search modes:
  keyword   Fast, no deps. Counts concept keyword hits per function.
  semantic  Requires sentence-transformers. Embeds concept + all functions,
            ranks by cosine similarity. Install is prompted on first use.
  combined  Both paths, weighted together (default).

Usage:
    python kleinos/apps/concept_search/app.py "<concept>" <target>
    python kleinos/apps/concept_search/app.py "walk a file tree and group files by extension" src/
    python kleinos/apps/concept_search/app.py "<concept>" <target> --mode keyword
    python kleinos/apps/concept_search/app.py "<concept>" <target> --install

Not wired into the main KleinBOTTLE app. Depends on kleinos/stdlib only.
sentence-transformers is optional; the app prompts to install it on first
semantic use and falls back to keyword mode until then.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deps
import searcher
import render


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Find existing Python functions that match a concept description.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("concept", help="Plain-language description of what you want to build")
    p.add_argument("target", help="Directory or .py file to search")
    p.add_argument(
        "--mode", choices=["keyword", "semantic", "combined"], default="combined",
        help="Search mode: combined (default) | keyword | semantic",
    )
    p.add_argument("--top-n", type=int, default=15, metavar="N",
                   help="Max candidates to show (default: 15)")
    p.add_argument("--min-lines", type=int, default=3, metavar="N",
                   help="Min function length to consider (default: 3)")
    p.add_argument(
        "--model", default="sentence-transformers/all-MiniLM-L6-v2", metavar="NAME",
        help="Sentence-transformers model name (default: all-MiniLM-L6-v2)",
    )
    p.add_argument("--install", action="store_true",
                   help="Install sentence-transformers without prompting")
    p.add_argument("--export", choices=["md", "json"], default="md",
                   help="Output format: md (default) or json")
    p.add_argument("--out", metavar="FILE",
                   help="Write report to FILE instead of stdout")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # --- Dep check for semantic modes ---
    effective_mode = args.mode
    if effective_mode in {"semantic", "combined"}:
        if args.install:
            # Non-interactive forced install
            if not deps.is_semantic_available():
                print("Installing sentence-transformers ...")
                ok = deps.prompt_install(interactive=False)
                if not ok:
                    if effective_mode == "semantic":
                        print("Cannot run semantic mode without sentence-transformers.")
                        return 1
                    effective_mode = "keyword"
                    print("Falling back to keyword mode.")
        elif not deps.is_semantic_available():
            ok = deps.ensure_semantic(interactive=True)
            if not ok:
                if effective_mode == "semantic":
                    return 1
                effective_mode = "keyword"

    report = searcher.build_report(
        concept=args.concept,
        target=args.target,
        mode=effective_mode,
        top_n=args.top_n,
        min_lines=args.min_lines,
        model_name=args.model,
    )

    output = render.as_json(report) if args.export == "json" else render.render_markdown(report)
    render.write_output(output, args.out)
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())

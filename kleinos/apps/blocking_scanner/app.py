"""Blocking Scanner — KleinOS app entry point.

Scans a directory for blocking calls (subprocess, time.sleep, requests.*,
socket.*, httpx.*, input, etc.) that can freeze a UI or async thread.

Usage:
    python kleinos/apps/blocking_scanner/app.py <target> [--export md|json] [--out FILE]
    python kleinos/apps/blocking_scanner/app.py --help

Not wired into the main KleinBOTTLE app. Depends on kleinos/stdlib only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scanner
import render


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scan a directory for blocking calls that can freeze a UI or async thread.",
    )
    p.add_argument("target", help="Directory or .py file to scan")
    p.add_argument("--extra", nargs="*", default=[], metavar="PATTERN",
                   help="Additional dotted call patterns to flag (e.g. mylib.fetch)")
    p.add_argument("--export", choices=["md", "json"], default="md",
                   help="Output format: md (default) or json")
    p.add_argument("--out", metavar="FILE",
                   help="Write report to FILE instead of stdout")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = scanner.build_report(args.target, extra_blocking=args.extra)
    output = render.as_json(report) if args.export == "json" else render.render_markdown(report)
    render.write_output(output, args.out)
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())

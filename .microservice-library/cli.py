"""
ms-toolbox CLI  —  list / describe / call microservices.

Usage:
  python cli.py list
  python cli.py describe ScoutMS
  python cli.py call ScoutMS scan_path root_path=/some/path depth=3
"""
import sys
import json
import argparse
import importlib.util
import inspect
from pathlib import Path

SERVICES_DIR = Path(__file__).parent / "services"
sys.path.insert(0, str(SERVICES_DIR))

from microservice_std_lib import extract_service_schema  # noqa: E402


# ── discovery ─────────────────────────────────────────────────────────────────

def discover() -> dict:
    registry = {}
    for f in sorted(SERVICES_DIR.glob("_*MS.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if getattr(cls, "_is_microservice", False):
                try:
                    schema = extract_service_schema(cls)
                    registry[schema["meta"]["name"]] = {"cls": cls, "schema": schema}
                except Exception:
                    pass
    return registry


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_list(registry: dict, _args) -> None:
    print(f"  {'SERVICE':<35} {'DESCRIPTION':<60}  TAGS")
    print("  " + "-" * 105)
    for svc_name, info in sorted(registry.items()):
        meta = info["schema"]["meta"]
        tags = ", ".join(meta.get("tags", []))
        desc = meta.get("description", "")[:58]
        print(f"  {svc_name:<35} {desc:<60}  {tags}")


def cmd_describe(registry: dict, args) -> None:
    info = registry.get(args.service)
    if not info:
        print(f"Unknown service: {args.service}")
        sys.exit(1)
    print(json.dumps(info["schema"], indent=2))


def cmd_call(registry: dict, args) -> None:
    info = registry.get(args.service)
    if not info:
        print(f"Unknown service: {args.service}")
        sys.exit(1)
    try:
        instance = info["cls"]()
    except TypeError as e:
        print(f"Cannot instantiate {args.service} with no args: {e}")
        sys.exit(1)
    method = getattr(instance, args.method, None)
    if method is None:
        print(f"No method '{args.method}' on {args.service}")
        sys.exit(1)
    kwargs: dict = {}
    for token in args.kwargs or []:
        k, _, v = token.partition("=")
        kwargs[k.lstrip("-")] = v
    try:
        result = method(**kwargs)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="ms-toolbox",
                                     description="Microservice toolbox CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all available services")

    p_desc = sub.add_parser("describe", help="Show full schema for a service")
    p_desc.add_argument("service", help="Service name (e.g. ScoutMS)")

    p_call = sub.add_parser("call", help="Call a service endpoint")
    p_call.add_argument("service", help="Service name")
    p_call.add_argument("method",  help="Method name")
    p_call.add_argument("kwargs",  nargs="*",
                        help="keyword=value pairs (e.g. root_path=/tmp depth=3)")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    registry = discover()
    {"list": cmd_list, "describe": cmd_describe, "call": cmd_call}[args.cmd](registry, args)


if __name__ == "__main__":
    main()

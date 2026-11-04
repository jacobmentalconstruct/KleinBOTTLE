"""
ms-toolbox MCP server — exposes every @service_endpoint as an MCP tool.

Each tool name is:  ServiceName__method_name
  e.g.  ScoutMS__scan_path

Run as an MCP stdio server:
  python mcp_server.py

Wire into your MCP client config:
  {
    "mcpServers": {
      "ms-toolbox": {
        "command": "python",
        "args": ["/path/to/ms_toolbox/mcp_server.py"]
      }
    }
  }

Requires:  pip install mcp
"""
import sys
import json
import importlib.util
import inspect
import asyncio
from pathlib import Path

SERVICES_DIR = Path(__file__).parent / "services"
sys.path.insert(0, str(SERVICES_DIR))

from microservice_std_lib import extract_service_schema  # noqa: E402

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types as mcp_types
except ImportError:
    print("ERROR: `mcp` package not found.  pip install mcp", file=sys.stderr)
    sys.exit(1)


# ── type coercion helper ───────────────────────────────────────────────────────

_TYPE_MAP = {
    "str": str, "string": str,
    "int": int, "integer": int,
    "float": float, "number": float,
    "bool": bool, "boolean": bool,
}

def _coerce(value: str, type_hint: str):
    fn = _TYPE_MAP.get(type_hint.lower().strip())
    if fn is bool:
        return value.lower() not in ("false", "0", "no", "")
    return fn(value) if fn else value


# ── discovery ─────────────────────────────────────────────────────────────────

def _discover() -> dict:
    """Returns {tool_name: {instance, method_name, schema_ep}}."""
    tools: dict = {}
    for f in sorted(SERVICES_DIR.glob("_*MS.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        for _name, cls in inspect.getmembers(mod, inspect.isclass):
            if not getattr(cls, "_is_microservice", False):
                continue
            try:
                schema = extract_service_schema(cls)
                instance = cls()
            except Exception:
                continue
            svc_name = schema["meta"]["name"]
            for ep in schema["endpoints"]:
                tool_name = f"{svc_name}__{ep['name']}"
                tools[tool_name] = {
                    "instance": instance,
                    "method": ep["name"],
                    "ep": ep,
                    "svc": svc_name,
                }
    return tools


_TOOLS = _discover()

server = Server("ms-toolbox")


# ── MCP handlers ──────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[mcp_types.Tool]:
    result = []
    for tool_name, info in sorted(_TOOLS.items()):
        ep = info["ep"]
        props = {
            k: {"type": "string", "description": v}
            for k, v in ep["inputs"].items()
        }
        result.append(mcp_types.Tool(
            name=tool_name,
            description=f"[{info['svc']}] {ep['description']}",
            inputSchema={
                "type": "object",
                "properties": props,
                "required": list(ep["inputs"].keys()),
            },
        ))
    return result


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    if name not in _TOOLS:
        return [mcp_types.TextContent(type="text", text=f"Unknown tool: {name}")]
    info = _TOOLS[name]
    ep   = info["ep"]
    method = getattr(info["instance"], info["method"])
    # coerce string args from MCP into declared types
    kwargs = {
        k: _coerce(str(v), ep["inputs"].get(k, "str"))
        for k, v in arguments.items()
    }
    try:
        result = method(**kwargs)
        return [mcp_types.TextContent(type="text",
                                      text=json.dumps(result, indent=2, default=str))]
    except Exception as exc:
        return [mcp_types.TextContent(type="text", text=f"Error calling {name}: {exc}")]


# ── entry point ───────────────────────────────────────────────────────────────

async def _main() -> None:
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())

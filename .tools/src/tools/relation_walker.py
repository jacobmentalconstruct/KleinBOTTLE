"""Navigate filesystem, Python code units, or caller-supplied hierarchies.

Drop into .tools/src/tools/relation_walker.py. Reuses the toolbox's existing
common.py CLI/result contract and existing file_tree_snapshot.py for filesystem input.
No Git, database, UI, model, or third-party dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import standard_main, tool_error, tool_result

FILE_METADATA = {
    "tool_name": "relation_walker",
    "version": "1.1.0",
    "entrypoint": "src/tools/relation_walker.py",
    "category": "introspection",
    "summary": "Inspect parent/child/sibling relations or compare two nodes in a filesystem or virtual hierarchy.",
    "mcp_name": "relation_walker",
    "input_schema": {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"type": "string", "enum": ["inspect", "relate"]},
            "project_root": {"type": "string", "description": "Directory filesystem mode (choose one input mode)."},
            "python_root": {"type": "string", "description": "Python code-unit mode: directory or .py file (choose one input mode)."},
            "min_lines": {"type": "integer", "default": 5, "description": "Python code-unit minimum function line count."},
            "nodes": {
                "type": "array",
                "description": "Virtual nodes with id, parent (ID or null), optional kind; choose one input mode.",
                "items": {"type": "object"},
            },
            "node": {"type": "string", "description": "Node ID for inspect."},
            "a": {"type": "string", "description": "First node ID for relate."},
            "b": {"type": "string", "description": "Second node ID for relate."},
            "max_depth": {"type": "integer", "default": 8, "description": "Filesystem scan depth."},
            "extra_ignore": {"type": "array", "items": {"type": "string"}},
            "descendant_depth": {"type": "integer", "default": 0, "description": "inspect: how many levels of descendants to return; 0 disables."},
            "max_results": {"type": "integer", "default": 100, "description": "Maximum entries in each inspect relation list."},
        },
    },
}


def _flatten_tree(tree: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Translate the existing file_tree_snapshot tree into generic nodes."""
    nodes = []
    truncated_count = 0
    stack = [(tree, None)]
    while stack:
        entry, parent = stack.pop()
        node_id = entry["path"].replace("\\", "/")
        nodes.append({"id": node_id, "parent": parent, "kind": entry.get("type", "node")})
        truncated_count += bool(entry.get("truncated", False))
        stack.extend((child, node_id) for child in reversed(entry.get("children", [])))
    return nodes, truncated_count


def _read_nodes(arguments: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read one source; keep the relationship logic independent of its origin."""
    if sum(key in arguments for key in ("nodes", "project_root", "python_root")) != 1:
        raise ValueError("Supply exactly one of nodes, project_root, or python_root.")
    if "nodes" in arguments:
        if not isinstance(arguments["nodes"], list):
            raise ValueError("'nodes' must be a list.")
        return arguments["nodes"], {"source": "virtual", "scan_truncated_count": 0}

    if "python_root" in arguments:
        from lib.python_code_units import collect_python_units, code_unit_nodes
        data = collect_python_units(
            arguments["python_root"], min_lines=arguments.get("min_lines", 5),
            extra_ignore=arguments.get("extra_ignore", []),
        )
        return code_unit_nodes(data["units"]), {
            "source": "python", "project_root": data["root"],
            "files_scanned": data["files_scanned"],
            "units_scanned": len(data["units"]),
            "read_errors": data["errors"], "scan_truncated_count": 0,
        }

    # Import only for the filesystem mode. This is already part of .tools.
    from tools.file_tree_snapshot import run as tree_snapshot

    snapshot = tree_snapshot({
        "project_root": arguments["project_root"],
        "max_depth": arguments.get("max_depth", 8),
        "extra_ignore": arguments.get("extra_ignore", []),
        "include_docstrings": False,
        "include_line_counts": False,
    })
    if snapshot.get("status") != "ok":
        raise ValueError(snapshot.get("result", {}).get("message", "Filesystem scan failed."))
    nodes, truncated_count = _flatten_tree(snapshot["result"]["tree"])
    return nodes, {
        "source": "filesystem",
        "project_root": snapshot["result"]["project_root"],
        "scan_truncated_count": truncated_count,
    }


def _index(nodes: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str | None], dict[str, list[str]]]:
    """Validate and index one forest. Keys are stable, caller-provided node IDs."""
    details: dict[str, dict[str, Any]] = {}
    parent_of: dict[str, str | None] = {}
    children_of: dict[str, list[str]] = {}
    for entry in nodes:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise ValueError("Every node must have a nonempty string 'id'.")
        node_id = entry["id"]
        parent = entry.get("parent")
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise ValueError(f"Invalid parent for {node_id!r}.")
        if node_id in details:
            raise ValueError(f"Duplicate node ID: {node_id!r}.")
        details[node_id] = {"id": node_id, "kind": entry.get("kind", "node")}
        parent_of[node_id] = parent
        children_of[node_id] = []

    for node_id, parent in parent_of.items():
        if parent is not None:
            if parent not in parent_of:
                raise ValueError(f"Missing parent {parent!r} for {node_id!r}.")
            children_of[parent].append(node_id)
    for child_ids in children_of.values():
        child_ids.sort()

    # One linear walk with completed-state memoization; reject cycles.
    state: dict[str, int] = {}  # 1 = exploring, 2 = complete
    for start in parent_of:
        current = start
        path = []
        while current is not None and state.get(current, 0) == 0:
            state[current] = 1
            path.append(current)
            current = parent_of[current]
        if current is not None and state.get(current) == 1:
            raise ValueError(f"Cycle found at {current!r}.")
        for item in path:
            state[item] = 2
    return details, parent_of, children_of


def _chain(node_id: str, parent_of: dict[str, str | None]) -> list[str]:
    """Node first, followed by parents until root."""
    if node_id not in parent_of:
        raise ValueError(f"Unknown node ID: {node_id!r}.")
    chain = []
    while node_id is not None:
        chain.append(node_id)
        node_id = parent_of[node_id]
    return chain


def _inspect(node_id: str, details: dict, parent_of: dict, children_of: dict, *,
             max_results: int, descendant_depth: int) -> dict[str, Any]:
    ancestors = _chain(node_id, parent_of)[1:][::-1]  # root first
    parent = parent_of[node_id]
    siblings = [] if parent is None else [item for item in children_of[parent] if item != node_id]
    children = children_of[node_id]
    descendants = []
    descendants_truncated = False
    if descendant_depth > 0:
        stack = [(child, 1) for child in reversed(children)]
        while stack:
            descendant, level = stack.pop()
            if len(descendants) == max_results:
                descendants_truncated = True
                break
            descendants.append(descendant)
            if level < descendant_depth:
                stack.extend((child, level + 1) for child in reversed(children_of[descendant]))
    return {
        "node": details[node_id],
        "parent": parent,
        "children": children[:max_results],
        "children_count": len(children),
        "siblings": siblings[:max_results],
        "siblings_count": len(siblings),
        "ancestors": ancestors[:max_results],
        "ancestors_count": len(ancestors),
        "descendants": descendants,
        "descendants_truncated": descendants_truncated,
        "depth": len(ancestors),
    }


def _relate(a: str, b: str, parent_of: dict[str, str | None]) -> dict[str, Any]:
    chain_a = _chain(a, parent_of)
    chain_b = _chain(b, parent_of)
    positions_a = {node: i for i, node in enumerate(chain_a)}
    common = next((node for node in chain_b if node in positions_a), None)
    if common is None:
        return {"a": a, "b": b, "relation": "disconnected", "common_ancestor": None,
                "distance": None, "path": None}
    i = positions_a[common]
    j = chain_b.index(common)
    if a == b:
        relation = "self"
    elif parent_of[b] == a:
        relation = "parent"  # a is b's parent
    elif parent_of[a] == b:
        relation = "child"   # a is b's child
    elif parent_of[a] == parent_of[b] and parent_of[a] is not None:
        relation = "siblings"
    elif i == 0:
        relation = "ancestor"  # a is b's ancestor
    elif j == 0:
        relation = "descendant"  # a is b's descendant
    else:
        relation = "related"
    path = chain_a[:i + 1] + list(reversed(chain_b[:j]))
    return {"a": a, "b": b, "relation": relation, "common_ancestor": common,
            "distance": i + j, "path": path}


def run(arguments: dict[str, Any]) -> dict[str, Any]:
    """Entry point used by the existing .tools CLI and MCP host."""
    name = FILE_METADATA["tool_name"]
    try:
        action = arguments.get("action")
        if action not in {"inspect", "relate"}:
            raise ValueError("'action' must be 'inspect' or 'relate'.")
        nodes, source_info = _read_nodes(arguments)
        details, parent_of, children_of = _index(nodes)
        if action == "inspect":
            node_id = arguments.get("node")
            max_results = arguments.get("max_results", 100)
            descendant_depth = arguments.get("descendant_depth", 0)
            if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
                raise ValueError("'max_results' must be a positive integer.")
            if not isinstance(descendant_depth, int) or isinstance(descendant_depth, bool) or descendant_depth < 0:
                raise ValueError("'descendant_depth' must be a nonnegative integer.")
            result = _inspect(node_id, details, parent_of, children_of,
                              max_results=max_results, descendant_depth=descendant_depth)
        else:
            result = _relate(arguments.get("a"), arguments.get("b"), parent_of)
        return tool_result(name, arguments, {
            **source_info,
            "node_count": len(details),
            "root_count": sum(parent is None for parent in parent_of.values()),
            **result,
        })
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        return tool_error(name, arguments, str(exc))


if __name__ == "__main__":
    standard_main(FILE_METADATA, run)

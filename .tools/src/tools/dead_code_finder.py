"""
FILE: dead_code_finder.py
ROLE: Find unused functions, classes, and imports in a Python project.
WHAT IT DOES:
  - AST-scans all .py files to build a definition index (functions, classes, imports)
  - Cross-references against all usages (calls, attribute access, name references)
  - Reports definitions that are never referenced from other locations
  - Distinguishes between truly dead code and plausible entry points
  - Zero write risk — purely read-only introspection
HOW TO USE:
  - python src/tools/dead_code_finder.py metadata
  - python src/tools/dead_code_finder.py run --input-json '{"project_root": "path/to/project"}'
  - python src/tools/dead_code_finder.py run --input-json '{"project_root": ".", "src_dir": "src", "include_imports": true}'
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))
from common import standard_main, tool_result, tool_error, collect_py_files

FILE_METADATA = {
    "tool_name": "dead_code_finder",
    "version": "1.0.0",
    "entrypoint": "src/tools/dead_code_finder.py",
    "category": "analysis",
    "summary": "Find unused functions, classes, and imports in a Python project by cross-referencing definitions against usages.",
    "mcp_name": "dead_code_finder",
    "input_schema": {
        "type": "object",
        "required": ["project_root"],
        "properties": {
            "project_root": {
                "type": "string",
                "description": "Path to the project root directory."
            },
            "src_dir": {
                "type": "string",
                "default": "",
                "description": "Subdirectory to scan (e.g. 'src'). If empty, scans from project_root."
            },
            "include_imports": {
                "type": "boolean",
                "default": True,
                "description": "If true, also report unused imports."
            },
            "ignore_prefixes": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["_", "test_"],
                "description": "Function/class name prefixes to exclude from dead code reporting (e.g. private or test functions)."
            },
            "entry_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Known entry point function names that should not be flagged (e.g. ['main', 'run', 'app'])."
            }
        }
    }
}

# Names that are plausible entry points or framework hooks — never flag these
BUILTIN_ENTRY_POINTS = {
    "main", "run", "app", "setup", "teardown", "configure",
    "__init__", "__enter__", "__exit__", "__call__", "__str__", "__repr__",
    "__len__", "__iter__", "__next__", "__getitem__", "__setitem__",
    "__eq__", "__hash__", "__lt__", "__le__", "__gt__", "__ge__",
    "__add__", "__sub__", "__mul__", "__bool__", "__contains__",
    "__del__", "__new__", "__post_init__",
}


def _extract_definitions(filepath: Path) -> list[dict[str, Any]]:
    """Extract function, class, and import definitions from a file."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    defs: list[dict[str, Any]] = []

    for node in ast.iter_child_nodes(tree):
        # Top-level functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append({
                "type": "function",
                "name": node.name,
                "line": node.lineno,
                "file": str(filepath),
            })

        # Classes and their methods
        elif isinstance(node, ast.ClassDef):
            defs.append({
                "type": "class",
                "name": node.name,
                "line": node.lineno,
                "file": str(filepath),
            })
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.append({
                        "type": "method",
                        "name": f"{node.name}.{item.name}",
                        "short_name": item.name,
                        "line": item.lineno,
                        "file": str(filepath),
                    })

        # Imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                defs.append({
                    "type": "import",
                    "name": local_name,
                    "module": alias.name,
                    "line": node.lineno,
                    "file": str(filepath),
                })

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local_name = alias.asname or alias.name
                defs.append({
                    "type": "import",
                    "name": local_name,
                    "module": f"{node.module or ''}.{alias.name}",
                    "line": node.lineno,
                    "file": str(filepath),
                })

    return defs


def _extract_usages(filepath: Path) -> set[str]:
    """Extract all name references in a file."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
            # Also capture the full dotted path for method references
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            if len(parts) > 1:
                names.add(f"{parts[-1]}.{parts[-2]}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)

    return names


def _extract_dunder_all(filepath: Path) -> set[str]:
    """Return names listed in __all__, if present."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    for node in ast.iter_child_nodes(tree):
        if (isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__all__"
                and isinstance(node.value, (ast.List, ast.Tuple))):
            return {
                elt.value if isinstance(elt, ast.Constant) and isinstance(elt.value, str) else ""
                for elt in node.value.elts
            } - {""}
    return set()


def run(arguments: dict) -> dict:
    project_root = Path(arguments["project_root"])
    src_dir = arguments.get("src_dir", "")
    scan_root = project_root / src_dir if src_dir else project_root
    include_imports = arguments.get("include_imports", True)
    ignore_prefixes = tuple(arguments.get("ignore_prefixes", ["_", "test_"]))
    extra_entry_points = set(arguments.get("entry_points", []))

    if not scan_root.is_dir():
        return tool_error(FILE_METADATA["tool_name"], arguments, f"Not a directory: {scan_root}")

    try:
        py_files = collect_py_files(scan_root)

        # Collect all definitions
        all_defs: list[dict] = []
        for f in py_files:
            all_defs.extend(_extract_definitions(f))

        # Collect per-file usages (Fix 7: cross-file scoping)
        # Key: str(filepath) → set of referenced names in that file
        file_usages: dict[str, set[str]] = {str(f): _extract_usages(f) for f in py_files}

        # Names exported via __all__ count as externally used (Fix 4)
        exported_names: set[str] = set()
        for f in py_files:
            exported_names.update(_extract_dunder_all(f))

        entry_points = BUILTIN_ENTRY_POINTS | extra_entry_points

        # Find unused definitions
        unused: list[dict] = []
        for defn in all_defs:
            dtype = defn["type"]
            name = defn["name"]
            short_name = defn.get("short_name", name)
            def_file = defn["file"]

            # Skip imports if not requested
            if dtype == "import" and not include_imports:
                continue

            # Skip ignored prefixes
            base_name = short_name if dtype == "method" else name
            if any(base_name.startswith(p) for p in ignore_prefixes):
                continue

            # Skip known entry points
            if base_name in entry_points:
                continue

            # Skip if exported via __all__
            if name in exported_names or short_name in exported_names:
                continue

            # Check if name appears in any file OTHER than its definition file
            name_used = any(
                (name in usages or short_name in usages)
                for fpath, usages in file_usages.items()
                if fpath != def_file
            )

            if not name_used:
                # Make path relative
                try:
                    defn["file"] = str(Path(defn["file"]).relative_to(scan_root))
                except ValueError:
                    pass
                unused.append(defn)

        # Sort by type then file
        unused.sort(key=lambda d: (d["type"], d["file"], d["line"]))

        # Summary by type
        type_counts: dict[str, int] = {}
        for u in unused:
            type_counts[u["type"]] = type_counts.get(u["type"], 0) + 1

        # Summary by file
        file_counts: dict[str, int] = {}
        for u in unused:
            file_counts[u["file"]] = file_counts.get(u["file"], 0) + 1

        result: dict[str, Any] = {
            "scan_root": str(scan_root),
            "files_scanned": len(py_files),
            "definitions_found": len(all_defs),
            "unused_count": len(unused),
            "by_type": type_counts,
            "by_file": dict(sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:15]),
            "unused": unused,
        }

        return tool_result(FILE_METADATA["tool_name"], arguments, result)

    except Exception as exc:
        return tool_error(FILE_METADATA["tool_name"], arguments, str(exc))


if __name__ == "__main__":
    standard_main(FILE_METADATA, run)

"""Python code-unit extraction for read-only toolbox analyzers.

One pass yields source locations, AST fingerprints, similarity text and parent
IDs. No imports from HuduORACLE, Git, NumPy, or other third-party packages.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import tokenize
from pathlib import Path
from typing import Any

from common import should_skip_dir



class _Bindings(ast.NodeVisitor):
    """Collect argument and assignment bindings in a function's own scope."""

    def __init__(self, args: ast.arguments, statements: list[ast.stmt]):
        self.names: list[str] = []
        self.disallowed: set[str] = set()
        for arg in (args.posonlyargs + args.args + args.kwonlyargs):
            self._add(arg.arg)
        for arg in (args.vararg, args.kwarg):
            if arg is not None:
                self._add(arg.arg)
        # Global/nonlocal declarations override apparent local stores.
        for stmt in statements:
            self.visit(stmt)
        self.names = [n for n in self.names if n not in self.disallowed]

    def _add(self, name: str) -> None:
        if name not in self.names:
            self.names.append(name)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.disallowed.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.disallowed.update(node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node.name)  # binding in this scope; not its inner parameters

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        pass


class _RenameLocals(ast.NodeTransformer):
    def __init__(self, names: list[str]):
        self.mapping = {name: f"_LOCAL_{i}" for i, name in enumerate(names)}

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.mapping:
            node.id = self.mapping[node.id]
        return node

    # Nested scopes are deliberately left intact; avoids unsafe renaming.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return node


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _fingerprints(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str, str]:
    body = _strip_docstring(node.body)
    module = ast.Module(body=copy.deepcopy(body), type_ignores=[])
    exact = ast.dump(module, annotate_fields=True, include_attributes=False)
    bindings = _Bindings(node.args, body)
    normalized = _RenameLocals(bindings.names).visit(copy.deepcopy(module))
    structural = ast.dump(normalized, annotate_fields=True, include_attributes=False)
    readable = ast.unparse(normalized)
    digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest(exact), digest(structural), readable


def collect_python_units(target: Path | str, *, min_lines: int = 5,
                         extra_ignore: tuple[str, ...] = (),
                         include_tests: bool = True) -> dict[str, Any]:
    """Scan a directory or .py file, returning deterministic code-unit records."""
    root = Path(target).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Target does not exist: {root}")
    if root.is_file() and root.suffix != ".py":
        raise ValueError("A file target must have a .py extension")
    if not root.is_file() and not root.is_dir():
        raise ValueError("Target must be a directory or Python file")
    if type(min_lines) is not int or min_lines < 1:
        raise ValueError("min_lines must be a positive integer")
    if not isinstance(extra_ignore, (list, tuple)) or not all(isinstance(x, str) for x in extra_ignore):
        raise ValueError("extra_ignore must contain directory-name strings")
    if type(include_tests) is not bool:
        raise ValueError("include_tests must be boolean")
    skip = set(extra_ignore)
    base = root if root.is_dir() else root.parent
    paths = sorted(root.rglob("*.py")) if root.is_dir() else [root]
    paths = [p for p in paths if not p.is_symlink() and not any(
        should_skip_dir(part) or part in skip or (not include_tests and part in {"tests", "test"})
        for part in p.relative_to(base).parts[:-1])
        and (include_tests or not p.name.startswith("test_"))]
    units: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        rel = path.relative_to(base).as_posix()
        try:
            with tokenize.open(path) as fh:
                source = fh.read()
            tree = ast.parse(source, filename=rel)
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            errors.append({"file": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue
        lines = source.splitlines()

        def walk(node: ast.AST, prefix: str = "") -> None:
            """Preserve lexical scopes while traversing all control-flow forms."""
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}.{node.name}" if prefix else node.name
                end = node.end_lineno or node.lineno
                length = end - node.lineno + 1
                if length >= min_lines and _strip_docstring(node.body):
                    exact, structural, normalized = _fingerprints(node)
                    kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                    if prefix:
                        kind = "async_method" if kind == "async_function" else "method"
                    units.append({
                        "id": f"{rel}::{qual}@L{node.lineno}",
                        "file": rel, "name": node.name, "qualified_name": qual,
                        "line": node.lineno, "end_line": end,
                        "line_count": length, "node_count": sum(1 for _ in ast.walk(node)),
                        "kind": kind,
                        "exact_fingerprint": exact,
                        "structural_fingerprint": structural,
                        "structural_source": normalized,
                        "source": "\n".join(lines[node.lineno-1:end]),
                    })
                for child in node.body:
                    walk(child, qual)
            elif isinstance(node, ast.ClassDef):
                qual = f"{prefix}.{node.name}" if prefix else node.name
                for child in node.body:
                    walk(child, qual)
            else:
                for child in ast.iter_child_nodes(node):
                    walk(child, prefix)

        walk(tree)
    units.sort(key=lambda u: (u["file"], u["line"], u["qualified_name"]))
    return {"root": str(base), "files_scanned": len(paths), "units": units, "errors": errors}


def public_unit(unit: dict[str, Any], *, include_source: bool = False) -> dict[str, Any]:
    """Small stable finding reference without embedding large source bodies."""
    fields = ("id", "file", "qualified_name", "kind", "line", "end_line", "line_count", "node_count")
    record = {k: unit[k] for k in fields}
    if include_source:
        record["source"] = unit["source"]
    return record


def code_unit_nodes(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project code units into relation_walker-compatible virtual nodes."""
    nodes: dict[str, dict[str, Any]] = {".": {"id": ".", "parent": None, "kind": "root"}}
    for unit in units:
        path = Path(unit["file"])
        parts = path.parts
        for i in range(1, len(parts) + 1):
            entry = "/".join(parts[:i])
            parent = "." if i == 1 else "/".join(parts[:i-1])
            nodes.setdefault(entry, {"id": entry, "parent": parent,
                                     "kind": "file" if i == len(parts) else "directory"})
        prefix = unit["file"]
        parts = unit["qualified_name"].split(".")
        for name in parts[:-1]:
            scope = prefix + "::" + name if "::" not in prefix else prefix + "." + name
            nodes.setdefault(scope, {"id": scope, "parent": prefix, "kind": "scope"})
            prefix = scope
        nodes[unit["id"]] = {"id": unit["id"], "parent": prefix, "kind": unit["kind"]}
    return sorted(nodes.values(), key=lambda n: n["id"])

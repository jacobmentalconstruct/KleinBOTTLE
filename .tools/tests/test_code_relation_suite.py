"""Offline self-tests for the .tools code/relation suite.

Run before installation: python tests/test_suite.py
Run in installed tree: python tests/test_suite.py
No model download or production files are modified.
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

try:
    import common  # noqa: F401 -- actual toolbox when installed
except ImportError:
    # Standalone ZIP does not replace the real toolbox's common.py.
    common = types.ModuleType("common")
    SKIPS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
    common.should_skip_dir = lambda name: name in SKIPS
    common.tool_result = lambda name, args, result, status="ok": {"status": status, "tool": name, "input": args, "result": result}
    common.tool_error = lambda name, args, message: common.tool_result(name, args, {"message": message}, status="error")
    common.standard_main = lambda *a, **k: None
    sys.modules["common"] = common

from lib.python_code_units import collect_python_units, code_unit_nodes
from tools import duplicate_code_finder, similar_code_finder, relation_walker


def fixture(root: Path) -> None:
    (root / "alpha.py").write_text('''
def base(x):
    amount = x + 1
    if amount > 10:
        amount *= 2
    return amount

def near(x):
    amount = x + 1
    if amount > 10:
        amount *= 2
    amount += 0
    return amount

def remove_user(x):
    amount = delete_user(x)
    if amount:
        return 1
    return 0

class Group:
    def method(self, x):
        amount = x + 1
        if amount > 10:
            amount *= 2
        return amount
''', encoding="utf-8")
    (root / "beta.py").write_text('''
def copied(x):
    amount=x+1
    if amount>10:
        amount*=2
    return amount

def renamed(value):
    result=value+1
    if result>10:
        result*=2
    return result

def load_user(x):
    amount = load_user_from_db(x)
    if amount:
        return 1
    return 0

def short(x):
    return x
''', encoding="utf-8")


class SuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture(self.root)

    def test_extract_and_normalize(self) -> None:
        u = collect_python_units(self.root, min_lines=5)["units"]
        d = {e["name"]: e for e in u}
        self.assertEqual(d["base"]["exact_fingerprint"], d["copied"]["exact_fingerprint"])
        self.assertNotEqual(d["base"]["exact_fingerprint"], d["renamed"]["exact_fingerprint"])
        self.assertEqual(d["base"]["structural_fingerprint"], d["renamed"]["structural_fingerprint"])
        self.assertNotEqual(d["remove_user"]["structural_fingerprint"], d["load_user"]["structural_fingerprint"])
        self.assertEqual(d["method"]["qualified_name"], "Group.method")
        self.assertNotIn("short", d)

    def test_duplicate_clusters(self) -> None:
        r = duplicate_code_finder.run({"target": str(self.root)})
        self.assertEqual(r["status"], "ok")
        exact = r["result"]["exact_clusters"]
        structural = r["result"]["structural_clusters"]
        self.assertTrue(any({"base", "copied"} <= {m["qualified_name"] for m in c["members"]} for c in exact))
        self.assertTrue(any({"base", "renamed"} <= {m["qualified_name"] for m in c["members"]} for c in structural))
        self.assertEqual(json.dumps(r["result"], sort_keys=True), json.dumps(duplicate_code_finder.run({"target": str(self.root)})["result"], sort_keys=True))

    def test_similar_candidates(self) -> None:
        r = similar_code_finder.run({"target": str(self.root), "threshold": 0.5, "top_n": 100})
        self.assertEqual(r["status"], "ok")
        pairs = [{c["a"]["qualified_name"], c["b"]["qualified_name"]} for c in r["result"]["candidates"]]
        self.assertIn({"base", "near"}, pairs)
        self.assertNotIn({"base", "renamed"}, pairs)  # structural duplicate excluded

    def test_invalid_inputs(self) -> None:
        self.assertEqual(similar_code_finder.run({"target": str(self.root), "threshold": 2})["status"], "error")
        self.assertEqual(duplicate_code_finder.run({"target": "missing-no-such-dir"})["status"], "error")

    def test_filesystem_adapter(self) -> None:
        from unittest.mock import patch
        fake = types.ModuleType("tools.file_tree_snapshot")
        def snapshot_run(args):
            self.assertFalse(args["include_docstrings"])
            self.assertFalse(args["include_line_counts"])
            return {"status": "ok", "result": {"project_root": str(self.root),
                "tree": {"path": ".", "type": "directory", "children": [
                    {"path": "src", "type": "directory", "children": [
                        {"path": "src/one.py", "type": "file"},
                        {"path": "src/two.py", "type": "file"}]}
                ]}}}
        fake.run = snapshot_run
        with patch.dict(sys.modules, {"tools.file_tree_snapshot": fake}):
            r = relation_walker.run({"action": "inspect", "project_root": str(self.root), "node": "src"})
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["result"]["children"], ["src/one.py", "src/two.py"])

    def test_virtual_relations(self) -> None:
        nodes = [{"id": "root", "parent": None}, {"id": "a", "parent": "root"},
                 {"id": "b", "parent": "root"}, {"id": "leaf", "parent": "a"}]
        r = relation_walker.run({"action": "inspect", "nodes": nodes, "node": "a", "descendant_depth": 2})
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["result"]["siblings"], ["b"])
        self.assertEqual(r["result"]["descendants"], ["leaf"])
        r = relation_walker.run({"action": "relate", "nodes": nodes, "a": "leaf", "b": "b"})
        self.assertEqual(r["result"]["common_ancestor"], "root")
        self.assertEqual(r["result"]["distance"], 3)
        invalid = [{"id": "a", "parent": "b"}, {"id": "b", "parent": "a"}]
        self.assertEqual(relation_walker.run({"action": "inspect", "nodes": invalid, "node": "a"})["status"], "error")

    def test_code_units_as_virtual_space(self) -> None:
        data = collect_python_units(self.root)
        nodes = code_unit_nodes(data["units"])
        idx = {x["id"]: x for x in nodes}
        self.assertIn("alpha.py::Group", idx)
        method_id = next(u["id"] for u in data["units"] if u["name"] == "method")
        self.assertEqual(idx[method_id]["parent"], "alpha.py::Group")
        r = relation_walker.run({"action": "inspect", "python_root": str(self.root), "node": method_id})
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["result"]["parent"], "alpha.py::Group")
        r2 = relation_walker.run({"action": "relate", "python_root": str(self.root),
                                   "a": next(u["id"] for u in data["units"] if u["name"] == "base"),
                                   "b": next(u["id"] for u in data["units"] if u["name"] == "renamed")})
        self.assertEqual(r2["result"]["common_ancestor"], ".")


if __name__ == "__main__":
    unittest.main(verbosity=2)

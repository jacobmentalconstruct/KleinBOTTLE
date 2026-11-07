"""Rank possible code-consolidation candidates by structural text or optional embeddings.

Stdlib difflib is the default. Embeddings require an already-installed local
sentence-transformers model; they never require a database or cloud API.
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import standard_main, tool_error, tool_result
from lib.python_code_units import collect_python_units, public_unit

FILE_METADATA = {
    "tool_name": "similar_code_finder",
    "version": "1.0.0",
    "entrypoint": "src/tools/similar_code_finder.py",
    "category": "introspection",
    "summary": "Rank non-identical Python functions for manual consolidation review using difflib or optional local embeddings.",
    "mcp_name": "similar_code_finder",
    "input_schema": {
        "type": "object", "required": ["target"],
        "properties": {
            "target": {"type": "string", "description": "Python project directory or .py file."},
            "method": {"type": "string", "enum": ["difflib", "embedding"], "default": "difflib"},
            "threshold": {"type": "number", "default": 0.8},
            "top_n": {"type": "integer", "default": 30},
            "max_units": {"type": "integer", "default": 250},
            "min_lines": {"type": "integer", "default": 5},
            "include_tests": {"type": "boolean", "default": True},
            "extra_ignore": {"type": "array", "items": {"type": "string"}},
            "model": {"type": "string", "default": "sentence-transformers/all-MiniLM-L6-v2"},
            "include_source": {"type": "boolean", "default": False},
        },
    },
}


def _text_tokens(source: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]", source)


def _candidate_pairs(units: list[dict], method: str, model_name: str):
    if method == "embedding":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ValueError("Optional dependency unavailable: install sentence-transformers to use embedding mode.") from exc
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
            # Keep one embedding per unit, no persistent index.
            vectors = model.encode([f"{u['qualified_name']}\n{u['source']}" for u in units],
                                   normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            raise ValueError(f"Local embedding model could not load/run ({model_name}): {exc}") from exc
        def score(i: int, j: int) -> float:
            return float(sum(float(a) * float(b) for a, b in zip(vectors[i], vectors[j])))
    else:
        tokens = [_text_tokens(u["structural_source"]) for u in units]
        def score(i: int, j: int) -> float:
            a, b = tokens[i], tokens[j]
            if not a or not b:
                return 0.0
            # Cheap bound: very different lengths cannot have a high ratio.
            if 2 * min(len(a), len(b)) / (len(a) + len(b)) < 0.4:
                return 0.0
            return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()

    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            a, b = units[i], units[j]
            if a["structural_fingerprint"] == b["structural_fingerprint"]:
                continue  # Already reported by duplicate_code_finder.
            yield i, j, score(i, j)


def run(arguments: dict) -> dict:
    name = FILE_METADATA["tool_name"]
    try:
        target = arguments.get("target", arguments.get("project_root"))
        if not target:
            raise ValueError("Provide 'target' (directory or .py file).")
        method = arguments.get("method", "difflib")
        if method not in {"difflib", "embedding"}:
            raise ValueError("method must be 'difflib' or 'embedding'")
        threshold = arguments.get("threshold", 0.8)
        top_n = arguments.get("top_n", 30)
        max_units = arguments.get("max_units", 250)
        include_source = arguments.get("include_source", False)
        if type(threshold) not in {int, float} or not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if type(top_n) is not int or top_n < 1:
            raise ValueError("top_n must be a positive integer")
        if type(max_units) is not int or max_units < 2:
            raise ValueError("max_units must be an integer >= 2")
        if type(include_source) is not bool:
            raise ValueError("include_source must be boolean")
        data = collect_python_units(target, min_lines=arguments.get("min_lines", 5),
                                    extra_ignore=arguments.get("extra_ignore", []),
                                    include_tests=arguments.get("include_tests", True))
        units = data["units"]
        if len(units) > max_units:
            raise ValueError(f"Found {len(units)} code units; maximum is {max_units}. Narrow target or increase max_units.")
        candidates = []
        for i, j, score in _candidate_pairs(units, method, arguments.get("model", "sentence-transformers/all-MiniLM-L6-v2")):
            if score >= threshold:
                candidates.append({
                    "score": round(max(0.0, min(1.0, score)), 5),
                    "a": public_unit(units[i], include_source=include_source),
                    "b": public_unit(units[j], include_source=include_source),
                })
        candidates.sort(key=lambda c: (-c["score"], c["a"]["id"], c["b"]["id"]))
        return tool_result(name, arguments, {
            "method": method, "files_scanned": data["files_scanned"],
            "units_scanned": len(units), "candidate_count": len(candidates),
            "candidates": candidates[:top_n], "results_truncated": len(candidates) > top_n,
            "read_errors": data["errors"],
            "qualification": "Candidate scores are similarity signals, not proof of equivalent behavior.",
        })
    except (ValueError, OSError, TypeError) as exc:
        return tool_error(name, arguments, str(exc))


if __name__ == "__main__":
    standard_main(FILE_METADATA, run)

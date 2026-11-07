"""Concept search — finds existing Python functions that match a concept description.

Two scoring paths, both using the same unit collection:

  keyword   Always available. Counts concept keyword hits in each function's
            source text. Fast, no deps, coarse signal.

  semantic  Requires sentence-transformers. Embeds the concept and all code
            units, ranks by cosine similarity. Fine-grained signal.

When both paths run, scores are combined into a single ranked list.

Responsibility: build a structured report dict. No rendering.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

_STDLIB = Path(__file__).resolve().parents[2] / "stdlib" / "src"
sys.path.insert(0, str(_STDLIB))
sys.path.insert(0, str(_STDLIB / "tools"))

from lib.python_code_units import collect_python_units, public_unit

# Common English stop words — not worth searching for these
_STOP = frozenset({
    "a", "an", "the", "and", "or", "not", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "it", "its", "be", "are",
    "was", "were", "that", "this", "which", "who", "i", "we", "you",
    "he", "she", "they", "do", "does", "did", "have", "has", "had",
    "can", "will", "would", "should", "could", "may", "might",
    "want", "need", "like", "use", "get", "make", "take", "give",
    "all", "any", "each", "every", "some", "no", "new", "if", "so",
})


def _extract_keywords(concept: str) -> list[str]:
    """Split concept into meaningful lowercase tokens."""
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*", concept.lower())
    return [t for t in tokens if t not in _STOP and len(t) > 2]


def _keyword_scores(units: list[dict], keywords: list[str]) -> dict[str, float]:
    """Return unit_id -> normalised keyword hit score (0–1)."""
    scores = {}
    for unit in units:
        text = (unit.get("source") or "").lower()
        name = unit.get("qualified_name", "").lower()
        combined = name + " " + text
        hits = sum(combined.count(kw) for kw in keywords)
        # Normalise by length so short functions aren't penalised
        line_count = max(unit.get("line_count", 1), 1)
        scores[unit["id"]] = hits / (1 + line_count * 0.1)
    return scores


def _semantic_scores(units: list[dict], concept: str,
                     model_name: str) -> dict[str, float]:
    """Return unit_id -> cosine similarity score (0–1) using local embeddings."""
    from sentence_transformers import SentenceTransformer  # deferred import

    model = SentenceTransformer(model_name)
    texts = [
        f"{u['qualified_name']}\n{u.get('source', '')}"
        for u in units
    ]
    all_texts = [concept] + texts
    vectors = model.encode(all_texts, normalize_embeddings=True, show_progress_bar=False)

    concept_vec = vectors[0]
    scores = {}
    for i, unit in enumerate(units):
        unit_vec = vectors[i + 1]
        sim = float(sum(float(a) * float(b) for a, b in zip(concept_vec, unit_vec)))
        scores[unit["id"]] = max(0.0, sim)
    return scores


def build_report(
    concept: str,
    target: str,
    *,
    mode: Literal["keyword", "semantic", "combined"] = "combined",
    top_n: int = 15,
    min_lines: int = 3,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> dict:
    keywords = _extract_keywords(concept)

    data = collect_python_units(
        target,
        min_lines=min_lines,
        include_tests=True,
        extra_ignore=[],
    )
    units = data["units"]

    report = {
        "mode": "concept_search",
        "search_mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(Path(target).resolve()),
        "concept": concept,
        "keywords": keywords,
        "parameters": {
            "mode": mode,
            "top_n": top_n,
            "min_lines": min_lines,
            "model": model_name if mode != "keyword" else None,
        },
        "scan": {
            "files_scanned": data.get("files_scanned", 0),
            "units_scanned": len(units),
        },
        "candidates": [],
        "errors": list(data.get("errors", [])),
    }

    if not units:
        return report

    # --- Score ---
    kw_scores: dict[str, float] = {}
    sem_scores: dict[str, float] = {}

    if mode in {"keyword", "combined"}:
        kw_scores = _keyword_scores(units, keywords)

    if mode in {"semantic", "combined"}:
        try:
            sem_scores = _semantic_scores(units, concept, model_name)
        except Exception as exc:
            report["errors"].append({"source": "semantic", "error": str(exc)})
            if mode == "semantic":
                return report
            # combined: fall back to keyword only

    # --- Combine ---
    unit_by_id = {u["id"]: u for u in units}
    all_ids = set(kw_scores) | set(sem_scores)

    candidates = []
    for uid in all_ids:
        kw = kw_scores.get(uid, 0.0)
        sem = sem_scores.get(uid, 0.0)

        if mode == "keyword":
            final = kw
        elif mode == "semantic":
            final = sem
        else:
            # Combined: semantic dominates when available, keyword breaks ties
            final = sem * 0.8 + kw * 0.2 if sem_scores else kw

        if final <= 0:
            continue

        unit = unit_by_id[uid]
        entry = public_unit(unit, include_source=False)
        entry["score"] = round(final, 5)
        entry["keyword_score"] = round(kw, 5) if kw_scores else None
        entry["semantic_score"] = round(sem, 5) if sem_scores else None
        candidates.append(entry)

    candidates.sort(key=lambda c: -c["score"])
    report["candidates"] = candidates[:top_n]
    report["results_truncated"] = len(candidates) > top_n
    return report

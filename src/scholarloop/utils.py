from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
SECRET_RE = re.compile(r"(sk|ark)-[A-Za-z0-9_\-]+")


def tokenize(text: str | None) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def f1_from_pr(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def metric_for_ranking(ranked_ids: list[int], gold_ids: set[int]) -> dict[str, float]:
    top10 = ranked_ids[:10]
    top20 = ranked_ids[:20]
    p10 = len(set(top10) & gold_ids) / 10.0
    r20 = len(set(top20) & gold_ids) / len(gold_ids) if gold_ids else 0.0
    return {"P@10": p10, "R@20": r20, "F1": f1_from_pr(p10, r20)}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def redact(text: str) -> str:
    return SECRET_RE.sub(r"\1-<redacted>", text)


def top_ids_from_scores(scores: np.ndarray, corpus_ids: np.ndarray, limit: int, indices: Iterable[int] | None = None) -> list[int]:
    if indices is None:
        n = min(limit, len(scores))
        if n <= 0:
            return []
        idx = np.argpartition(-scores, n - 1)[:n]
    else:
        idx = np.array(list(indices), dtype=np.int64)
    ordered = sorted(idx.tolist(), key=lambda i: (-float(scores[i]), int(corpus_ids[i])))
    return [int(corpus_ids[i]) for i in ordered[:limit]]


def score_ranking(scores: np.ndarray, corpus_ids: np.ndarray, indices: Iterable[int]) -> list[int]:
    return top_ids_from_scores(scores, corpus_ids, limit=len(list(indices)) if not isinstance(indices, list) else len(indices), indices=indices)


def normalize_values(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values.astype(np.float32)
    lo = float(np.min(values))
    hi = float(np.max(values))
    if hi - lo <= 1e-12:
        return np.zeros_like(values, dtype=np.float32)
    return ((values - lo) / (hi - lo)).astype(np.float32)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.array(values, dtype=np.float64), q))

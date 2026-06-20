from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from scholarloop.rank.fusion import RankedResult
from scholarloop.utils import f1_from_pr, normalize_values


FEATURES = ("bm25", "dense_v2", "sub_bm25", "sub_dense_v2", "cross_encoder")


@dataclass(frozen=True)
class FusionV2Config:
    weights: dict[str, float]
    candidate_top_k: int = 100
    cross_top_n: int = 60
    final_k: int = 100

    def normalized_weights(self) -> dict[str, float]:
        vals = {k: float(self.weights.get(k, 0.0)) for k in FEATURES}
        total = sum(max(0.0, v) for v in vals.values())
        if total <= 0:
            return {k: (1.0 if k == "bm25" else 0.0) for k in FEATURES}
        return {k: max(0.0, v) / total for k, v in vals.items()}


def deterministic_query_split(query_ids: Iterable[str]) -> dict[str, str]:
    """60/20/20 split by stable hash; independent of current result quality."""
    split: dict[str, str] = {}
    for qid in query_ids:
        bucket = int(hashlib.sha256(qid.encode("utf-8")).hexdigest()[:8], 16) % 10
        if bucket < 6:
            split[qid] = "train"
        elif bucket < 8:
            split[qid] = "holdout"
        else:
            split[qid] = "test"
    return split


def build_feature_matrix(
    pool_indices: list[int],
    bm25_scores: np.ndarray,
    dense_scores: np.ndarray,
    sub_bm25_scores: np.ndarray,
    sub_dense_scores: np.ndarray,
    cross_scores_by_index: dict[int, float],
) -> np.ndarray:
    idx = np.array(pool_indices, dtype=np.int64)
    cols = [
        normalize_values(bm25_scores[idx]),
        normalize_values(dense_scores[idx]),
        normalize_values(sub_bm25_scores[idx]),
        normalize_values(sub_dense_scores[idx]),
    ]
    cross_raw = np.array([cross_scores_by_index.get(int(i), np.nan) for i in pool_indices], dtype=np.float32)
    if np.isfinite(cross_raw).any():
        finite = np.isfinite(cross_raw)
        norm = np.zeros_like(cross_raw, dtype=np.float32)
        norm[finite] = normalize_values(cross_raw[finite])
        cols.append(norm)
    else:
        cols.append(np.zeros(len(pool_indices), dtype=np.float32))
    return np.vstack(cols).T.astype(np.float32)


def rank_with_features(
    pool_indices: list[int],
    corpus_ids: np.ndarray,
    features: np.ndarray,
    config: FusionV2Config,
) -> list[RankedResult]:
    weights = config.normalized_weights()
    w = np.array([weights[k] for k in FEATURES], dtype=np.float32)
    scores = features @ w
    order = sorted(range(len(pool_indices)), key=lambda pos: (-float(scores[pos]), int(corpus_ids[pool_indices[pos]])))
    rows: list[RankedResult] = []
    for pos in order[: config.final_k]:
        idx = pool_indices[pos]
        parts = [f"{name}={features[pos, j]:.3f}*{w[j]:.2f}" for j, name in enumerate(FEATURES)]
        rows.append(RankedResult(corpusid=int(corpus_ids[idx]), score=float(scores[pos]), reason="; ".join(parts)))
    return rows


def metric_with_ndcg(ranked_ids: list[int], gold_ids: set[int], k: int = 20) -> dict[str, float]:
    top10 = ranked_ids[:10]
    top20 = ranked_ids[:20]
    p10 = len(set(top10) & gold_ids) / 10.0
    r20 = len(set(top20) & gold_ids) / len(gold_ids) if gold_ids else 0.0
    dcg = 0.0
    for rank, cid in enumerate(top20, start=1):
        if cid in gold_ids:
            dcg += 1.0 / np.log2(rank + 1)
    ideal_hits = min(len(gold_ids), k)
    idcg = sum(1.0 / np.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 0.0
    return {"P@10": float(p10), "R@20": float(r20), "F1": float(f1_from_pr(p10, r20)), "NDCG@20": float(ndcg)}


def candidate_weight_grid(include_cross: bool = True) -> list[FusionV2Config]:
    configs: list[FusionV2Config] = []
    bm25_vals = [0.10, 0.20, 0.30, 0.40]
    dense_vals = [0.30, 0.40, 0.50, 0.60, 0.70]
    sub_vals = [0.00, 0.05, 0.10, 0.15]
    cross_vals = [0.00, 0.05, 0.10, 0.20, 0.30] if include_cross else [0.00]
    seen = set()
    for bm in bm25_vals:
        for de in dense_vals:
            for sb in sub_vals:
                for sd in sub_vals:
                    for ce in cross_vals:
                        raw = {"bm25": bm, "dense_v2": de, "sub_bm25": sb, "sub_dense_v2": sd, "cross_encoder": ce}
                        cfg = FusionV2Config(weights=raw)
                        norm = tuple(round(cfg.normalized_weights()[k], 4) for k in FEATURES)
                        if norm not in seen:
                            seen.add(norm)
                            configs.append(FusionV2Config(weights=dict(zip(FEATURES, norm))))
    return configs

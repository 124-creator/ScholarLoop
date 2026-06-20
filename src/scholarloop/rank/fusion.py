from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scholarloop.utils import normalize_values


@dataclass(frozen=True)
class RankedResult:
    corpusid: int
    score: float
    reason: str


class FusionRanker:
    def __init__(self, corpus_ids: np.ndarray, id_to_index: dict[int, int], weights: dict[str, float] | None = None) -> None:
        self.corpus_ids = corpus_ids
        self.id_to_index = id_to_index
        # Weight diagnostic on the full LitSearch corpus (reports/m010_diag)
        # showed BM25 0.4 + neural 0.6 has a positive paired-bootstrap CI
        # against BM25 alone. Subquery signals are still computed and exposed in
        # reasons, but do not change the final score in this first production
        # module because small LLM subquery weights regressed the smoke set.
        self.weights = weights or {"bm25": 0.40, "dense": 0.60, "sub_bm25": 0.0, "sub_dense": 0.0}

    def rank(self, pool_ids: list[int], bm25_scores: np.ndarray, dense_scores: np.ndarray, sub_bm25_scores: list[np.ndarray] | None = None, sub_dense_scores: list[np.ndarray] | None = None) -> list[RankedResult]:
        indices = [self.id_to_index[cid] for cid in pool_ids if cid in self.id_to_index]
        if not indices:
            return []
        idx = np.array(indices, dtype=np.int64)
        bm = normalize_values(bm25_scores[idx])
        de = normalize_values(dense_scores[idx])
        sb = np.zeros_like(bm)
        sd = np.zeros_like(de)
        if sub_bm25_scores:
            sb = np.max(np.vstack([normalize_values(s[idx]) for s in sub_bm25_scores]), axis=0)
        if sub_dense_scores:
            sd = np.max(np.vstack([normalize_values(s[idx]) for s in sub_dense_scores]), axis=0)
        score = self.weights["bm25"]*bm + self.weights["dense"]*de + self.weights["sub_bm25"]*sb + self.weights["sub_dense"]*sd
        rows=[]
        for pos, i in enumerate(indices):
            parts = [f"bm25={bm[pos]:.3f}", f"dense={de[pos]:.3f}"]
            if sub_bm25_scores:
                parts.append(f"sub_bm25={sb[pos]:.3f}")
            if sub_dense_scores:
                parts.append(f"sub_dense={sd[pos]:.3f}")
            rows.append(RankedResult(corpusid=int(self.corpus_ids[i]), score=float(score[pos]), reason="; ".join(parts)))
        rows.sort(key=lambda r: (-r.score, r.corpusid))
        return rows

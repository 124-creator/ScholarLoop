from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from scholarloop.retrieval.bm25 import BM25Retriever
from scholarloop.retrieval.dense_v2 import DenseV2Retriever
from scholarloop.utils import normalize_values


@dataclass(frozen=True)
class IterativeRetrievalResult:
    query_id: str
    retrieval_queries: list[str]
    candidate_ids: list[int]
    new_candidate_ids: list[int]
    score_by_id: dict[int, float]
    evidence: dict[str, Any]


class IterativeRetriever:
    """A-v3 gold-blind whole-corpus re-retriever.

    It receives generated subqueries and searches the full offline corpus with
    both BM25 and DenseV2.  It never accepts gold ids.
    """

    def __init__(
        self,
        corpus_ids: np.ndarray,
        bm25: BM25Retriever,
        dense: DenseV2Retriever,
        bm25_weight: float = 0.45,
        dense_weight: float = 0.55,
    ) -> None:
        self.corpus_ids = corpus_ids.astype(np.int64)
        self.bm25 = bm25
        self.dense = dense
        self.bm25_weight = float(bm25_weight)
        self.dense_weight = float(dense_weight)

    def retrieve(
        self,
        query_id: str,
        query: str,
        subqueries: list[str],
        initial_ids: list[int],
        top_k_per_query: int = 80,
        final_candidate_k: int = 80,
    ) -> IterativeRetrievalResult:
        retrieval_queries = []
        for q in [query, *subqueries]:
            text = " ".join(str(q).split())
            if text and text not in retrieval_queries:
                retrieval_queries.append(text)

        scores = np.zeros(len(self.corpus_ids), dtype=np.float32)
        source_hits: dict[str, list[int]] = {}
        n = min(top_k_per_query, len(self.corpus_ids))
        for pos, rq in enumerate(retrieval_queries):
            bm25_scores = self.bm25.bm25_scores(rq)
            dense_scores = self.dense.scores(rq)
            combined = self.bm25_weight * normalize_values(bm25_scores) + self.dense_weight * normalize_values(dense_scores)
            # Later subqueries are slightly discounted; they still add genuine
            # whole-corpus retrieval evidence without drowning the original query.
            discount = 1.0 if pos == 0 else 0.92
            scores = np.maximum(scores, (combined * discount).astype(np.float32))
            idx = np.argpartition(-combined, n - 1)[:n]
            ordered_idx = sorted(idx.tolist(), key=lambda i: (-float(combined[i]), int(self.corpus_ids[i])))
            source_hits[rq] = [int(self.corpus_ids[i]) for i in ordered_idx[: min(20, n)]]

        # Force the first-stage A-v2 candidates to remain available, but score
        # them through the same vector so this is not just re-ranking an old list.
        initial_set = {int(cid) for cid in initial_ids}
        idx = np.argpartition(-scores, min(final_candidate_k * 4, len(scores)) - 1)[: min(final_candidate_k * 4, len(scores))]
        ordered_idx = sorted(idx.tolist(), key=lambda i: (-float(scores[i]), int(self.corpus_ids[i])))
        ranked = [int(self.corpus_ids[i]) for i in ordered_idx if float(scores[i]) > 0.0]
        merged: list[int] = []
        for cid in [*initial_ids, *ranked]:
            cid = int(cid)
            if cid not in merged:
                merged.append(cid)
            if len(merged) >= final_candidate_k:
                break
        new_ids = [cid for cid in merged if cid not in initial_set]
        score_by_id = {int(self.corpus_ids[i]): float(scores[i]) for i in ordered_idx[: min(final_candidate_k * 4, len(ordered_idx))]}
        return IterativeRetrievalResult(
            query_id=query_id,
            retrieval_queries=retrieval_queries,
            candidate_ids=merged,
            new_candidate_ids=new_ids,
            score_by_id=score_by_id,
            evidence={
                "searched_entire_corpus": True,
                "corpus_size": int(len(self.corpus_ids)),
                "top_k_per_query": int(top_k_per_query),
                "final_candidate_k": int(final_candidate_k),
                "new_candidate_count": int(len(new_ids)),
                "source_hits_top20": source_hits,
            },
        )

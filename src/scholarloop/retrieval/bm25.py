from __future__ import annotations

import math

import numpy as np
from rank_bm25 import BM25Okapi

from scholarloop.utils import tokenize


def keyword_scores(query_tokens: list[str], doc_token_sets: list[set[str]]) -> np.ndarray:
    qset = set(query_tokens)
    scores = np.zeros(len(doc_token_sets), dtype=np.float32)
    if not qset:
        return scores
    for i, toks in enumerate(doc_token_sets):
        overlap = qset & toks
        if overlap:
            scores[i] = len(overlap) / math.sqrt(max(1, len(toks)))
    return scores


class BM25Retriever:
    def __init__(self, docs: list[str]) -> None:
        self.doc_tokens = [tokenize(t) for t in docs]
        self.doc_token_sets = [set(toks) for toks in self.doc_tokens]
        self.bm25 = BM25Okapi(self.doc_tokens)

    def bm25_scores(self, query: str) -> np.ndarray:
        return np.array(self.bm25.get_scores(tokenize(query)), dtype=np.float32)

    def keyword_scores(self, query: str) -> np.ndarray:
        return keyword_scores(tokenize(query), self.doc_token_sets)

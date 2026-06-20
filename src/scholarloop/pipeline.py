from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from scholarloop.corpus import LitSearchCorpus, QueryRecord
from scholarloop.llm import LLMClient
from scholarloop.query import QueryDecomposer
from scholarloop.rank import FusionRanker, RankedResult
from scholarloop.retrieval import BM25Retriever, DenseRetriever
from scholarloop.utils import top_ids_from_scores


class ScholarLoopPipeline:
    def __init__(self, root: Path = Path("."), report_dir: Path = Path("reports/m010"), top_k: int = 100, prompt_k: int = 12) -> None:
        self.root = Path(root)
        self.report_dir = Path(report_dir)
        self.top_k = top_k
        self.prompt_k = prompt_k
        self.repo = LitSearchCorpus(root)
        self.corpus = self.repo.load_corpus()
        self.repo.validate_gold()
        self.corpus_ids = self.repo.corpus_ids
        self.docs = self.corpus["text"].tolist()
        self.bm25 = BM25Retriever(self.docs)
        self.dense = DenseRetriever(self.docs, self.report_dir / "cache")
        self.llm = LLMClient(self.report_dir / "raw" / "llm")
        self.decomposer = QueryDecomposer(self.llm)
        self.fusion = FusionRanker(self.corpus_ids, self.repo.id_to_index)

    def baseline_scores(self, query: str) -> dict[str, np.ndarray]:
        return {"keyword": self.bm25.keyword_scores(query), "bm25": self.bm25.bm25_scores(query), "neural_embedding": self.dense.scores(query)}

    def candidate_pool(self, scores: dict[str, np.ndarray]) -> list[int]:
        pool = set()
        for s in scores.values():
            pool.update(top_ids_from_scores(s, self.corpus_ids, self.top_k))
        return sorted(pool)

    def single_llm_rank(self, query_id: str, query: str, pool_ids: list[int], combined_scores: np.ndarray) -> tuple[list[int], int, dict[str, Any]]:
        indices = [self.repo.id_to_index[cid] for cid in pool_ids]
        ordered = sorted(indices, key=lambda i: (-float(combined_scores[i]), int(self.corpus_ids[i])))[:self.prompt_k]
        lines=[]
        allowed=set(pool_ids)
        for i in ordered:
            row=self.corpus.iloc[i]
            title=str(row["title"])[:180]
            abstract=" ".join(str(row["abstract"]).split())[:40]
            lines.append(f"- {int(row['corpusid'])}: {title}. Abs: {abstract}")
        system="You are an academic paper retrieval baseline. Return strict JSON only. Choose relevant papers only from candidate corpus IDs. Do not invent papers. Output final JSON only."
        user=f"Query:\n{query}\n\nCandidate papers (choose only these corpus IDs):\n" + "\n".join(lines) + "\n\nReturn JSON only: {\"ranked_corpusids\": [up to 20 corpus IDs ordered from most to least relevant]}."
        parsed, meta = self.llm.chat_json(f"single_{query_id}", system, user, {"query_id":query_id, "arm":"single", "candidate_count":len(ordered)})
        values = parsed.get("ranked_corpusids") if isinstance(parsed, dict) else parsed
        ranked=[]; hallucinated=0; seen=set()
        for value in values or []:
            try:
                cid=int(str(value.get("corpusid") if isinstance(value, dict) else value).strip())
            except Exception:
                hallucinated += 1; continue
            if cid not in allowed:
                hallucinated += 1; continue
            if cid not in seen:
                ranked.append(cid); seen.add(cid)
        return ranked, hallucinated, meta

    def scholarloop_rank(self, query: QueryRecord, pool_ids: list[int], base_scores: dict[str, np.ndarray]) -> tuple[list[RankedResult], dict[str, Any]]:
        decomp = self.decomposer.decompose(query.query_id, query.query)
        sub_bm25=[]; sub_dense=[]
        for subq in decomp.subqueries:
            sub_bm25.append(self.bm25.bm25_scores(subq))
        if decomp.subqueries:
            sub_dense = [row for row in self.dense.batch_scores(list(decomp.subqueries))]
        ranked = self.fusion.rank(pool_ids, base_scores["bm25"], base_scores["neural_embedding"], sub_bm25, sub_dense)
        return ranked, {"subqueries": list(decomp.subqueries), "criteria": list(decomp.criteria), "meta": decomp.meta}

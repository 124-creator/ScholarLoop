from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scholarloop.llm import LLMClient


@dataclass(frozen=True)
class ListwiseRerankResult:
    query_id: str
    ranked_ids: list[int]
    llm_returned_ids: list[int]
    llm_out_of_pool_ids: list[int]
    llm_meta: dict[str, Any]
    fallback_used: bool


def _clip(text: str, limit: int = 520) -> str:
    return " ".join((text or "").split())[:limit]


def _parse_ranked_ids(parsed: Any) -> list[int]:
    values: Any = []
    if isinstance(parsed, dict):
        values = parsed.get("ranked_ids") or parsed.get("ranking") or parsed.get("ids") or []
    elif isinstance(parsed, list):
        values = parsed
    out: list[int] = []
    for item in values:
        try:
            cid = int(item)
        except Exception:
            continue
        if cid not in out:
            out.append(cid)
    return out


class LLMListwiseReranker:
    """Gold-blind listwise reranker for M090 A-v3 candidates."""

    def __init__(self, llm: LLMClient, candidate_limit: int = 20) -> None:
        self.llm = llm
        self.candidate_limit = candidate_limit

    def rerank(self, query_id: str, query: str, candidates: list[dict[str, Any]]) -> ListwiseRerankResult:
        limited = candidates[: self.candidate_limit]
        pool_ids = [int(c["corpusid"]) for c in limited]
        pool = set(pool_ids)
        payload = [
            {
                "corpusid": int(c["corpusid"]),
                "title": _clip(str(c.get("title", "")), 220),
                "abstract": _clip(str(c.get("abstract", "")), 520),
                "source": str(c.get("source", "")),
            }
            for c in limited
        ]
        system = (
            "You are a gold-blind academic search reranker. Rank only the "
            "provided candidate corpusids by relevance to the query. Do not add "
            "new ids, authors, years, DOIs, or papers. Return one JSON object "
            "with key ranked_ids containing the candidate corpusids in best-first order."
        )
        user = (
            f"Query:\n{query}\n\n"
            "Candidate papers:\n"
            f"{payload}\n\n"
            "Return JSON only. ranked_ids must be a permutation/subset of the given corpusids."
        )
        parsed, meta = self.llm.chat_json(
            name=f"m090_listwise_{query_id}",
            system=system,
            user=user,
            prompt_info={
                "module": "m090.llm_listwise_reranker",
                "query_id": query_id,
                "candidate_count": len(pool_ids),
                "candidate_ids": pool_ids,
                "gold_blind": True,
                "contains_gold": False,
            },
            max_tokens=2048,
        )
        returned = _parse_ranked_ids(parsed)
        out_of_pool = [cid for cid in returned if cid not in pool]
        ranked: list[int] = []
        for cid in returned:
            if cid in pool and cid not in ranked:
                ranked.append(cid)
        for cid in pool_ids:
            if cid not in ranked:
                ranked.append(cid)
        return ListwiseRerankResult(
            query_id=query_id,
            ranked_ids=ranked,
            llm_returned_ids=returned,
            llm_out_of_pool_ids=out_of_pool,
            llm_meta=meta,
            fallback_used=not bool(returned),
        )

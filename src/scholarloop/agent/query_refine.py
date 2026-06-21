from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scholarloop.llm import LLMClient


@dataclass(frozen=True)
class QueryRefinement:
    query_id: str
    subqueries: list[str]
    rationale: str
    llm_meta: dict[str, Any]


def _clip(text: str, limit: int = 700) -> str:
    return " ".join((text or "").split())[:limit]


def _clean_subqueries(values: Any, original_query: str, max_subqueries: int) -> list[str]:
    cleaned: list[str] = []
    if isinstance(values, str):
        values = [values]
    if isinstance(values, list):
        for item in values:
            text = " ".join(str(item).split())
            if not text or text.lower() == original_query.lower():
                continue
            if text not in cleaned:
                cleaned.append(text[:240])
            if len(cleaned) >= max_subqueries:
                break
    return cleaned


class IterativeQueryAgent:
    """Generate follow-up retrieval subqueries from top candidate content.

    The agent accepts only query text plus candidate titles/abstracts.  It has
    no parameter for gold ids or relevance labels, which keeps the call surface
    gold-blind by construction.
    """

    def __init__(self, llm: LLMClient, max_subqueries: int = 3) -> None:
        self.llm = llm
        self.max_subqueries = max_subqueries

    def refine(self, query_id: str, query: str, top_docs: list[dict[str, Any]]) -> QueryRefinement:
        system = (
            "You refine academic literature-search queries. Use only the user "
            "query and the provided candidate paper titles/abstracts. Do not "
            "invent paper ids, authors, years, DOIs, or labels. Return one JSON "
            "object with keys subqueries (array of short search strings) and rationale."
        )
        docs = []
        for i, doc in enumerate(top_docs[:8], start=1):
            docs.append(
                {
                    "slot": i,
                    "corpusid": int(doc["corpusid"]),
                    "title": _clip(str(doc.get("title", "")), 220),
                    "abstract": _clip(str(doc.get("abstract", "")), 650),
                }
            )
        user = (
            "Original query:\n"
            f"{query}\n\n"
            "Top retrieved candidate papers (not gold labels):\n"
            f"{docs}\n\n"
            f"Create up to {self.max_subqueries} refined/expanded search subqueries "
            "that should retrieve additional real papers from the same offline corpus. "
            "Return JSON only."
        )
        parsed, meta = self.llm.chat_json(
            name=f"m090_refine_{query_id}",
            system=system,
            user=user,
            prompt_info={
                "module": "m090.iterative_query_agent",
                "query_id": query_id,
                "candidate_count": len(docs),
                "gold_blind": True,
                "contains_gold": False,
            },
            max_tokens=2048,
        )
        subqueries = _clean_subqueries(parsed.get("subqueries") if isinstance(parsed, dict) else [], query, self.max_subqueries)
        if not subqueries:
            # Deterministic fallback still performs real re-retrieval and is
            # explicitly reported by the caller.
            subqueries = [query]
        rationale = ""
        if isinstance(parsed, dict):
            rationale = " ".join(str(parsed.get("rationale", "")).split())[:500]
        return QueryRefinement(query_id=query_id, subqueries=subqueries, rationale=rationale, llm_meta=meta)

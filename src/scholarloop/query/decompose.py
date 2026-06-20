from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scholarloop.llm import LLMClient


@dataclass(frozen=True)
class Decomposition:
    subqueries: tuple[str, ...]
    criteria: tuple[str, ...]
    meta: dict[str, Any]


class QueryDecomposer:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def decompose(self, query_id: str, query: str) -> Decomposition:
        system = "You decompose complex academic search queries. Return strict JSON only. Do not name or invent papers. Output final JSON only."
        user = f"Complex paper search query:\n{query}\n\nReturn JSON only: {{\"subqueries\": [3 concise retrieval subqueries], \"criteria\": [short relevance criteria]}}."
        parsed, meta = self.llm.chat_json(f"decompose_{query_id}", system, user, {"query_id": query_id, "arm": "decompose"}, max_tokens=1024)
        subqs = self._parse_list(parsed, "subqueries", "queries")[:4] or [query]
        criteria = self._parse_list(parsed, "criteria")[:5]
        return Decomposition(tuple(subqs), tuple(criteria), meta)

    @staticmethod
    def _parse_list(parsed: Any, *keys: str) -> list[str]:
        values: Any = []
        if isinstance(parsed, dict):
            for key in keys:
                if parsed.get(key):
                    values = parsed[key]
                    break
        elif isinstance(parsed, list):
            values = parsed
        out = []
        for item in values or []:
            if isinstance(item, dict):
                item = item.get("query") or item.get("text") or item.get("criterion")
            if isinstance(item, str) and item.strip():
                out.append(item.strip()[:300])
        return out

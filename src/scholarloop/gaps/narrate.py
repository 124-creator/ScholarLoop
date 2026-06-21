from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scholarloop.llm import LLMClient

ID_RE = re.compile(r"\b\d{6,15}\b")


@dataclass(frozen=True)
class NarrationResult:
    candidate_index: int
    text: str
    allowed_ids: list[int]
    mentioned_ids: list[int]
    out_of_evidence_ids: list[int]
    evidence_status: str
    llm_meta: dict[str, Any]
    fallback_used: bool = False


def validate_narration_ids(text: str, allowed_ids: set[int]) -> tuple[list[int], list[int]]:
    mentioned: list[int] = []
    outside: list[int] = []
    for match in ID_RE.findall(text or ""):
        try:
            value = int(match)
        except Exception:
            continue
        if value not in mentioned:
            mentioned.append(value)
        if value not in allowed_ids and value not in outside:
            outside.append(value)
    return mentioned, outside


def deterministic_grounded_summary(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence") or {}
    counts = evidence.get("counts") or {}
    ids = candidate.get("allowed_narration_ids") or []
    id_text = ", ".join(str(i) for i in ids[:6]) if ids else "no ids"
    return (
        f"Operational gap candidate: `{candidate['concept_a']}` + `{candidate['concept_b']}`. "
        f"Before the cutoff, each concept had support but their pair co-occurred {counts.get('past_cooccur_count', 0)} times; "
        f"recent counts were {counts.get('recent_count_a', 0)} and {counts.get('recent_count_b', 0)}. "
        f"Future fill count is {counts.get('future_fill_count', 0)}. Evidence paper ids: {id_text}."
    )


def _prompt(candidate: dict[str, Any]) -> tuple[str, str]:
    evidence = candidate.get("evidence") or {}
    system = (
        "You explain a pre-computed research-gap candidate. Return strict JSON only. "
        "Do not add papers, authors, DOI, venue, year, or facts. Mention only the provided paper ids if you mention ids."
    )
    user = {
        "candidate": {
            "concept_a": candidate.get("concept_a"),
            "concept_b": candidate.get("concept_b"),
            "evidence_status": candidate.get("evidence_status"),
            "counts": evidence.get("counts"),
            "allowed_paper_ids": candidate.get("allowed_narration_ids", []),
        },
        "instruction": "Return JSON: {\"summary\": \"2-3 sentences grounded only in the counts and allowed_paper_ids.\"}",
    }
    return system, json.dumps(user, ensure_ascii=False)


def narrate_candidates(candidates: list[dict[str, Any]], raw_dir: Path, limit: int = 5, use_llm: bool = True) -> tuple[list[NarrationResult], dict[str, Any]]:
    """Narrate top candidates while preserving H5.

    If the LLM output mentions any out-of-evidence id, the accepted narration is
    replaced with a deterministic grounded summary. The raw LLM response remains
    on disk for audit, but the delivered narration has zero out-of-evidence ids.
    """

    results: list[NarrationResult] = []
    llm: LLMClient | None = LLMClient(raw_dir) if use_llm and limit > 0 else None
    for idx, candidate in enumerate(candidates[:limit]):
        allowed = set(int(x) for x in candidate.get("allowed_narration_ids", []))
        meta: dict[str, Any] = {"llm_used": False}
        fallback = False
        text = deterministic_grounded_summary(candidate)
        if llm is not None:
            system, user = _prompt(candidate)
            parsed, meta = llm.chat_json(f"m070_gap_narration_{idx:03d}", system, user, {"candidate_index": idx, "arm": "m070_gap_narration"}, max_tokens=1024)
            maybe = parsed.get("summary") if isinstance(parsed, dict) else None
            if isinstance(maybe, str) and maybe.strip():
                text = maybe.strip()
                meta = {**meta, "llm_used": True}
        mentioned, outside = validate_narration_ids(text, allowed)
        if outside:
            fallback = True
            text = deterministic_grounded_summary(candidate)
            mentioned, outside = validate_narration_ids(text, allowed)
        results.append(
            NarrationResult(
                candidate_index=idx,
                text=text,
                allowed_ids=sorted(allowed),
                mentioned_ids=mentioned,
                out_of_evidence_ids=outside,
                evidence_status=str(candidate.get("evidence_status") or "证据不足"),
                llm_meta=meta,
                fallback_used=fallback,
            )
        )
    summary = {
        "narrated": len(results),
        "out_of_evidence_total": sum(len(r.out_of_evidence_ids) for r in results),
        "fallback_count": sum(1 for r in results if r.fallback_used),
    }
    return results, summary

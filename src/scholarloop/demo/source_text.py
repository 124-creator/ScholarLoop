from __future__ import annotations

from functools import lru_cache
from typing import Any

from scholarloop.evidence.source import EvidenceSource
from scholarloop.evidence.status import STATUS_NEEDS_REVIEW, text_fields

VERIFIABLE_SOURCE_FIELDS = {"title", "abstract", "full_paper"}


@lru_cache(maxsize=1)
def source_adapter() -> EvidenceSource:
    return EvidenceSource()


@lru_cache(maxsize=4096)
def load_source_texts(corpusid: int) -> dict[str, str]:
    paper = source_adapter().get_paper(int(corpusid))
    return text_fields(paper)


def slice_by_span(source_text: str, span: Any) -> str | None:
    if not isinstance(span, list) or len(span) != 2:
        return None
    try:
        start, end = int(span[0]), int(span[1])
    except (TypeError, ValueError):
        return None
    if start < 0 or end < start or end > len(source_text):
        return None
    return source_text[start:end]


def verify_value_span(corpusid: int, field: dict[str, Any], value_key: str = "value") -> dict[str, Any]:
    """Verify one evidence field against read-only LitSearch source text.

    The highlighter may only be enabled when:
    source_text[char_span] == field[value_key].
    Otherwise the caller must display an explicit manual-review state.
    """

    source_field = field.get("source_field")
    span = field.get("char_span")
    expected = "" if field.get(value_key) is None else str(field.get(value_key))
    status = str(field.get("status") or STATUS_NEEDS_REVIEW)
    base = {
        "corpusid": int(corpusid),
        "field": field.get("field") or field.get("criterion") or value_key,
        "status": status,
        "source_field": source_field,
        "char_span": span,
        "value": expected,
        "confidence": field.get("confidence"),
        "highlightable": False,
        "mismatch": False,
        "manual_review_reason": None,
    }
    if source_field not in VERIFIABLE_SOURCE_FIELDS:
        return base | {
            "status": STATUS_NEEDS_REVIEW if not source_field else status,
            "manual_review_reason": "source_field missing or not locally verifiable",
        }
    source_text = load_source_texts(int(corpusid)).get(str(source_field), "")
    actual = slice_by_span(source_text, span)
    if actual is None:
        return base | {
            "source_length": len(source_text),
            "manual_review_reason": "char_span missing or outside source_text",
        }
    if actual != expected:
        return base | {
            "source_length": len(source_text),
            "actual_slice": actual,
            "mismatch": True,
            "manual_review_reason": "source_text[char_span] != value; not highlighted",
        }
    start, end = int(span[0]), int(span[1])
    return base | {
        "source_length": len(source_text),
        "highlightable": True,
        "mismatch": False,
        "highlight_text": actual,
        "source_preview": {
            "before": source_text[max(0, start - 220):start],
            "highlight": actual,
            "after": source_text[end:min(len(source_text), end + 220)],
        },
    }


def source_record_for_display(corpusid: int, source_field: str) -> dict[str, Any]:
    texts = load_source_texts(int(corpusid))
    return {
        "corpusid": int(corpusid),
        "source_field": source_field,
        "source_text": texts.get(source_field, ""),
        "source_length": len(texts.get(source_field, "")),
    }

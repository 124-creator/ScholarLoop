from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from scholarloop.corpus import LitSearchCorpus
from scholarloop.llm import LLMClient
from scholarloop.query.decompose import QueryDecomposer
from scholarloop.rank.fusion_v2 import FusionV2Config, build_feature_matrix, rank_with_features
from scholarloop.rank.rerank import CrossEncoderReranker
from scholarloop.retrieval.bm25 import BM25Retriever
from scholarloop.retrieval.dense_v2 import DEFAULT_DENSE_V2_MODEL, DenseV2Retriever
from scholarloop.utils import top_ids_from_scores


REALTIME_ENV = "SCHOLARLOOP_REALTIME_ENABLED"
DEFAULT_DISABLED_MESSAGE = "实时模式默认关闭；设置 SCHOLARLOOP_REALTIME_ENABLED=1 后才会运行在线 LLM/检索。"
DEFAULT_TIMEOUT_S = 180.0


@dataclass
class RealtimeRuntime:
    repo: LitSearchCorpus
    corpus: Any
    corpus_ids: np.ndarray
    docs: list[str]
    bm25: BM25Retriever
    dense: DenseV2Retriever
    cross: CrossEncoderReranker


_RUNTIME_LOCK = threading.RLock()
_RUNTIME_CACHE: RealtimeRuntime | None = None
_PRECHECK_CACHE: dict[str, Any] | None = None


def realtime_enabled() -> bool:
    return os.environ.get(REALTIME_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def unavailable(
    reason: str = DEFAULT_DISABLED_MESSAGE,
    *,
    enabled: bool = False,
    elapsed_s: float = 0.0,
    llm_calls: int = 0,
    tokens: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "m100.realtime_response.v1",
        "mode": "realtime_optional",
        "enabled": enabled,
        "status": "unavailable",
        "reason": reason,
        "notice": "实时结果非 verified 承重；失败时不编造推荐。",
        "cost": {"llm_calls": llm_calls, "tokens": tokens, "latency_s": elapsed_s},
        "results": [],
    }


def clear_realtime_runtime_cache() -> None:
    """Clear in-process caches. Intended for tests and deterministic equivalence checks."""

    global _RUNTIME_CACHE, _PRECHECK_CACHE
    with _RUNTIME_LOCK:
        _RUNTIME_CACHE = None
        _PRECHECK_CACHE = None


def _build_runtime() -> RealtimeRuntime:
    repo = LitSearchCorpus(Path("."))
    corpus = repo.load_corpus()
    corpus_ids = repo.corpus_ids
    docs = corpus["text"].tolist()
    bm25 = BM25Retriever(docs)
    dense = DenseV2Retriever(
        docs,
        cache_dir=Path("reports/m040/cache/dense_v2"),
        model_name=DEFAULT_DENSE_V2_MODEL,
        batch_size=64,
        device="cpu",
        local_files_only=False,
    )
    cross = CrossEncoderReranker(Path("reports/m100/cache/realtime_rerank"), batch_size=16, device="cpu")
    return RealtimeRuntime(repo=repo, corpus=corpus, corpus_ids=corpus_ids, docs=docs, bm25=bm25, dense=dense, cross=cross)


def _runtime(use_runtime_cache: bool = True) -> tuple[RealtimeRuntime, bool]:
    global _RUNTIME_CACHE
    if not use_runtime_cache:
        return _build_runtime(), False
    with _RUNTIME_LOCK:
        if _RUNTIME_CACHE is None:
            _RUNTIME_CACHE = _build_runtime()
            return _RUNTIME_CACHE, False
        return _RUNTIME_CACHE, True


def warm_realtime_cache() -> dict[str, Any]:
    start = time.perf_counter()
    _, reused = _runtime(use_runtime_cache=True)
    return {"status": "ok", "cache_reused": reused, "elapsed_s": time.perf_counter() - start}


def _precheck(llm: LLMClient, use_runtime_cache: bool) -> dict[str, Any]:
    global _PRECHECK_CACHE
    if use_runtime_cache and _PRECHECK_CACHE is not None:
        cached = dict(_PRECHECK_CACHE)
        cached["cached"] = True
        return cached
    result = dict(llm.precheck())
    result["cached"] = False
    if use_runtime_cache and result.get("valid"):
        _PRECHECK_CACHE = dict(result)
    return result


def _max_or_zero(arrays: list[np.ndarray], length: int) -> np.ndarray:
    if not arrays:
        return np.zeros(length, dtype=np.float32)
    return np.max(np.vstack(arrays), axis=0).astype(np.float32)


def _pool_from_scores(scores: list[np.ndarray], corpus_ids: np.ndarray, top_k: int) -> list[int]:
    pool: set[int] = set()
    for score in scores:
        pool.update(top_ids_from_scores(score, corpus_ids, top_k))
    return sorted(pool)


def run_realtime_query(query: str, limit: int = 10, timeout_s: float = DEFAULT_TIMEOUT_S, use_runtime_cache: bool = True) -> dict[str, Any]:
    started = time.perf_counter()
    query = " ".join((query or "").split())
    if not query:
        return unavailable("缺少 q 参数；未运行实时检索。")
    if not realtime_enabled():
        return unavailable()
    try:
        raw_dir = Path("reports/m100/raw/realtime_llm")
        llm = LLMClient(raw_dir, max_tokens=2048)
        precheck = _precheck(llm, use_runtime_cache)
        precheck_usage = precheck.get("usage") or {}
        precheck_tokens = int(precheck_usage.get("total_tokens") or 0) if isinstance(precheck_usage, dict) else 0
        precheck_calls = 0 if precheck.get("cached") else 1
        if not precheck.get("valid"):
            return unavailable(
                "LLM precheck failed；实时不可用，未编造结果。",
                enabled=True,
                elapsed_s=time.perf_counter() - started,
                llm_calls=precheck_calls,
                tokens=precheck_tokens,
            ) | {"precheck": precheck}
        decomposer = QueryDecomposer(llm)
        qid = "realtime_" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
        decomp = decomposer.decompose(qid, query)
        runtime, runtime_cache_reused = _runtime(use_runtime_cache=use_runtime_cache)
        repo = runtime.repo
        corpus = runtime.corpus
        corpus_ids = runtime.corpus_ids
        bm25 = runtime.bm25
        dense = runtime.dense
        bm25_scores = bm25.bm25_scores(query)
        dense_scores = dense.scores(query)
        subqueries = list(decomp.subqueries)[:4] or [query]
        sub_bm25 = _max_or_zero([bm25.bm25_scores(q) for q in subqueries], len(corpus_ids))
        sub_dense = _max_or_zero([row for row in dense.batch_scores(subqueries)], len(corpus_ids))
        pool_ids = _pool_from_scores([bm25_scores, dense_scores, sub_bm25, sub_dense], corpus_ids, top_k=80)
        pool_indices = [repo.id_to_index[cid] for cid in pool_ids]
        pre_features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25, sub_dense, {})
        pre_cfg = FusionV2Config(weights={"bm25": 0.1, "dense_v2": 0.4, "sub_bm25": 0.15, "sub_dense_v2": 0.15, "cross_encoder": 0.0}, final_k=80)
        pre_ranked = rank_with_features(pool_indices, corpus_ids, pre_features, pre_cfg)
        cross_ids = [r.corpusid for r in pre_ranked[:20]]
        cross_scores_by_id = runtime.cross.score(qid, query, cross_ids, corpus, repo.id_to_index)
        cross_scores_by_index = {repo.id_to_index[cid]: score for cid, score in cross_scores_by_id.items() if cid in repo.id_to_index}
        features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25, sub_dense, cross_scores_by_index)
        cfg = FusionV2Config(weights={"bm25": 0.1, "dense_v2": 0.4, "sub_bm25": 0.15, "sub_dense_v2": 0.15, "cross_encoder": 0.2}, final_k=limit)
        ranked = rank_with_features(pool_indices, corpus_ids, features, cfg)
        rows = []
        for rank, item in enumerate(ranked[:limit], start=1):
            doc = repo.get(item.corpusid)
            rows.append(
                {
                    "rank": rank,
                    "corpusid": item.corpusid,
                    "score": item.score,
                    "title": "" if doc is None else doc.title,
                    "abstract_preview": "" if doc is None else doc.abstract[:320],
                    "reason": item.reason,
                    "authors_year": {"status": "需人工核验", "resolution_hint": "realtime connector not run in M100 smoke"},
                    "source_or_doi": {"status": "需人工核验", "resolution_hint": "realtime connector not run in M100 smoke"},
                }
            )
        usage = decomp.meta.get("usage") or {}
        decomp_tokens = int(usage.get("total_tokens") or 0) if isinstance(usage, dict) else 0
        decomp_calls = 0 if decomp.meta.get("cached") else 1
        tokens = precheck_tokens + decomp_tokens
        llm_calls = precheck_calls + decomp_calls
        elapsed = time.perf_counter() - started
        budget_exceeded = elapsed > timeout_s
        return {
            "schema_version": "m100.realtime_response.v1",
            "mode": "realtime_optional",
            "enabled": True,
            "status": "ok",
            "notice": "实时结果非 verified 承重；用于演示新查询能力，成本和延时需单独披露。" + (" 本次超过展示预算但已完成真实排序，未丢弃已算结果。" if budget_exceeded else ""),
            "query": query,
            "decomposition": {"subqueries": list(decomp.subqueries), "criteria": list(decomp.criteria)},
            "results": rows,
            "cost": {"llm_calls": llm_calls, "tokens": tokens, "latency_s": elapsed},
            "source": {"corpus": "LitSearch corpus_clean", "ranker": "A-v2-compatible realtime path"},
            "cache": {"runtime_reused": runtime_cache_reused, "precheck_cached": bool(precheck.get("cached")), "decomposition_cached": bool(decomp.meta.get("cached"))},
            "budget": {"timeout_s": timeout_s, "elapsed_s": elapsed, "exceeded": budget_exceeded, "completed_results_not_discarded": True},
        }
    except Exception as exc:
        return unavailable(
            f"实时不可用：{type(exc).__name__}；未编造结果。",
            enabled=realtime_enabled(),
            elapsed_s=time.perf_counter() - started,
        ) | {"exception": str(exc)[:300]}

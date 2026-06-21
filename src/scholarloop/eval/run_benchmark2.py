from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import scholarloop.config as config  # noqa: F401 - import loads approved local env values.
from scholarloop.benchmarks.realscholarquery import RealScholarQueryCorpus
from scholarloop.llm import LLMClient
from scholarloop.query.decompose import QueryDecomposer
from scholarloop.rank.fusion_v2 import (
    FEATURES,
    FusionV2Config,
    build_feature_matrix,
    candidate_weight_grid,
    deterministic_query_split,
    metric_with_ndcg,
    rank_with_features,
)
from scholarloop.rank.rerank import DEFAULT_RERANK_MODEL, CrossEncoderReranker
from scholarloop.retrieval.dense_v2 import DEFAULT_DENSE_V2_MODEL, DenseV2Retriever
from scholarloop.utils import normalize_values, percentile, read_json, score_ranking, tokenize, top_ids_from_scores, write_json

SYSTEMS = ["keyword", "bm25", "neural_embedding_v2", "single_llm", "scholarloop_a_v2_no_rerank", "scholarloop_a_v2"]
FROZEN_WEIGHTS = {"bm25": 0.1, "dense_v2": 0.4, "sub_bm25": 0.15, "sub_dense_v2": 0.15, "cross_encoder": 0.2}
NO_RERANK_WEIGHTS = {"bm25": 0.14288571142885712, "dense_v2": 0.4285571442855714, "sub_bm25": 0.2142785721427857, "sub_dense_v2": 0.2142785721427857, "cross_encoder": 0.0}
PRE_RERANK_WEIGHTS = {"bm25": 0.25, "dense_v2": 0.55, "sub_bm25": 0.10, "sub_dense_v2": 0.10, "cross_encoder": 0.0}


@dataclass
class PreparedQuery:
    query_id: str
    query: str
    split: str
    resolvable_gold: set[int]
    full_gold: set[int]
    pool_ids: list[int]
    pool_indices: list[int]
    features: np.ndarray
    baseline_rankings: dict[str, list[int]]
    elapsed_s: float
    cross_candidate_count: int
    decomposition: list[str]
    single_llm_meta: dict[str, Any]
    single_llm_hallucinated: int


class SparseQueryTermIndex:
    """Memory-bounded keyword/BM25 scorer for a fixed small query vocabulary."""

    def __init__(self, docs: list[str], needed_terms: set[str], cache_dir: Path | None = None) -> None:
        self.docs_count = len(docs)
        self.needed_terms = set(needed_terms)
        self.doc_len = np.zeros(self.docs_count, dtype=np.float32)
        self.doc_unique_len = np.ones(self.docs_count, dtype=np.float32)
        self.postings: dict[str, list[tuple[int, int]]] = {term: [] for term in sorted(self.needed_terms)}
        start = time.perf_counter()
        for idx, text in enumerate(docs):
            toks = tokenize(text)
            self.doc_len[idx] = max(1, len(toks))
            unique = set(toks)
            self.doc_unique_len[idx] = max(1, len(unique))
            if not unique:
                continue
            counts: dict[str, int] = {}
            for tok in toks:
                if tok in self.needed_terms:
                    counts[tok] = counts.get(tok, 0) + 1
            for tok, tf in counts.items():
                self.postings[tok].append((idx, tf))
        self.avgdl = float(np.mean(self.doc_len)) if self.docs_count else 1.0
        self.elapsed_s = time.perf_counter() - start
        if cache_dir is not None:
            write_json(cache_dir / "sparse_query_index_meta.json", self.metadata())

    def metadata(self) -> dict[str, Any]:
        return {
            "docs_count": self.docs_count,
            "needed_terms": len(self.needed_terms),
            "nonempty_terms": sum(1 for v in self.postings.values() if v),
            "avgdl": self.avgdl,
            "elapsed_s": self.elapsed_s,
            "implementation": "query-vocabulary postings; deterministic BM25Okapi formula; avoids full-corpus token matrix materialization",
        }

    def bm25_scores(self, query: str) -> np.ndarray:
        scores = np.zeros(self.docs_count, dtype=np.float32)
        terms = tokenize(query)
        if not terms:
            return scores
        q_terms = sorted(set(terms))
        k1 = 1.5
        b = 0.75
        for term in q_terms:
            postings = self.postings.get(term) or []
            df = len(postings)
            if df == 0:
                continue
            idf = np.log(1.0 + (self.docs_count - df + 0.5) / (df + 0.5))
            for idx, tf in postings:
                denom = tf + k1 * (1.0 - b + b * float(self.doc_len[idx]) / self.avgdl)
                scores[idx] += float(idf * (tf * (k1 + 1.0) / denom))
        return scores

    def keyword_scores(self, query: str) -> np.ndarray:
        scores = np.zeros(self.docs_count, dtype=np.float32)
        q_terms = sorted(set(tokenize(query)))
        for term in q_terms:
            postings = self.postings.get(term) or []
            for idx, _tf in postings:
                scores[idx] += 1.0
        nonzero = scores > 0
        scores[nonzero] = scores[nonzero] / np.sqrt(self.doc_unique_len[nonzero])
        return scores


def usage_tokens(meta: dict[str, Any]) -> int:
    usage = meta.get("usage") or {}
    if not isinstance(usage, dict):
        return 0
    total = usage.get("total_tokens")
    if total is not None:
        try:
            return int(total)
        except Exception:
            return 0
    return int(usage.get("prompt_tokens", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def max_or_zero(arrays: list[np.ndarray], length: int) -> np.ndarray:
    if not arrays:
        return np.zeros(length, dtype=np.float32)
    return np.max(np.vstack(arrays), axis=0).astype(np.float32)


def pool_from_sources(scores: list[np.ndarray], corpus_ids: np.ndarray, top_k: int) -> list[int]:
    pool: set[int] = set()
    for score in scores:
        pool.update(top_ids_from_scores(score, corpus_ids, top_k))
    return sorted(pool)


def ranking_from_features(pool_indices: list[int], corpus_ids: np.ndarray, features: np.ndarray, cfg: FusionV2Config) -> list[int]:
    weights = cfg.normalized_weights()
    w = np.array([weights[k] for k in FEATURES], dtype=np.float32)
    scores = features @ w
    ids = corpus_ids[np.array(pool_indices, dtype=np.int64)]
    order = np.lexsort((ids, -scores))
    return [int(ids[i]) for i in order[: cfg.final_k]]


def aggregate(rows: list[dict[str, Any]], system: str) -> dict[str, Any]:
    subset = [r for r in rows if r["system"] == system]
    out: dict[str, Any] = {"system": system, "queries": len(subset)}
    for metric in ["P@10", "R@20", "F1", "NDCG@20"]:
        out[metric] = float(statistics.mean(float(r[metric]) for r in subset)) if subset else 0.0
    out["hallucinated_or_out_of_pool"] = int(sum(int(r.get("hallucinated_or_out_of_pool", 0) or 0) for r in subset))
    out["total_tokens"] = int(sum(int(r.get("total_tokens", 0) or 0) for r in subset))
    out["latency_s"] = float(sum(float(r.get("latency_s", 0.0) or 0.0) for r in subset))
    return out


def aggregate_by_split(rows: list[dict[str, Any]], splits: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for split in ["train", "holdout", "test"]:
        split_rows = [r for r in rows if splits.get(r["query_id"]) == split]
        out[split] = [aggregate(split_rows, system) for system in SYSTEMS]
    return out


def paired_bootstrap(a: list[float], b: list[float], n: int = 10000, seed: int = 42) -> dict[str, Any]:
    diffs = np.array(a, dtype=np.float64) - np.array(b, dtype=np.float64)
    rng = np.random.default_rng(seed)
    if len(diffs) == 0:
        return {"mean_delta": 0.0, "ci95": [0.0, 0.0], "resamples": n, "passed": False}
    samples = rng.choice(diffs, size=(n, len(diffs)), replace=True).mean(axis=1)
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return {"mean_delta": float(diffs.mean()), "ci95": [float(lo), float(hi)], "resamples": n, "passed": bool(lo > 0)}


def paired_permutation(a: list[float], b: list[float], n: int = 10000, seed: int = 43) -> dict[str, Any]:
    diffs = np.array(a, dtype=np.float64) - np.array(b, dtype=np.float64)
    if len(diffs) == 0:
        return {"mean_delta": 0.0, "p_one_sided": 1.0, "resamples": n, "passed": False}
    observed = float(diffs.mean())
    if observed <= 0:
        return {"mean_delta": observed, "p_one_sided": 1.0, "resamples": n, "passed": False}
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0], dtype=np.float64), size=(n, len(diffs)), replace=True)
    null_means = (signs * diffs).mean(axis=1)
    p = float((np.sum(null_means >= observed) + 1) / (n + 1))
    return {"mean_delta": observed, "p_one_sided": p, "resamples": n, "passed": bool(p < 0.05)}


def significance_for(rows: list[dict[str, Any]], bootstrap_n: int) -> dict[str, Any]:
    by_q: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_q.setdefault(row["query_id"], {})[row["system"]] = row
    a = [float(sysrows["scholarloop_a_v2"]["F1"]) for _qid, sysrows in sorted(by_q.items()) if "scholarloop_a_v2" in sysrows and "bm25" in sysrows]
    b = [float(sysrows["bm25"]["F1"]) for _qid, sysrows in sorted(by_q.items()) if "scholarloop_a_v2" in sysrows and "bm25" in sysrows]
    boot = paired_bootstrap(a, b, n=bootstrap_n)
    perm = paired_permutation(a, b, n=bootstrap_n)
    return {"a_v2_vs_bm25_f1": {"bootstrap": boot, "permutation": perm, "passed": bool(boot["passed"] or perm["passed"])}}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["scope", "query_id", "split", "system", "P@10", "R@20", "F1", "NDCG@20", "hallucinated_or_out_of_pool", "total_tokens", "latency_s"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def single_llm_rank(
    llm: LLMClient,
    query_id: str,
    query: str,
    pool_ids: list[int],
    pool_indices: list[int],
    corpus,
    corpus_ids: np.ndarray,
    pre_scores: np.ndarray,
    prompt_k: int,
) -> tuple[list[int], int, dict[str, Any]]:
    allowed = set(int(x) for x in pool_ids)
    ordered_indices = sorted(pool_indices, key=lambda i: (-float(pre_scores[i]), int(corpus_ids[i])))[:prompt_k]
    lines: list[str] = []
    for idx in ordered_indices:
        row = corpus.iloc[idx]
        title = " ".join(str(row["title"]).split())[:180]
        abstract = " ".join(str(row["abstract"]).split())[:80]
        lines.append(f"- {int(row['corpusid'])}: {title}. Abs: {abstract}")
    system = "You are an academic paper retrieval baseline. Return strict JSON only. Choose relevant papers only from candidate corpus IDs. Do not invent papers. Output final JSON only."
    user = (
        f"Query:\n{query}\n\nCandidate papers (choose only these corpus IDs):\n"
        + "\n".join(lines)
        + "\n\nReturn JSON only: {\"ranked_corpusids\": [up to 20 corpus IDs ordered from most to least relevant]}."
    )
    parsed, meta = llm.chat_json(f"m060_single_{query_id}", system, user, {"query_id": query_id, "arm": "m060_single", "candidate_count": len(ordered_indices)}, max_tokens=2048)
    values = parsed.get("ranked_corpusids") if isinstance(parsed, dict) else parsed
    ranked: list[int] = []
    seen: set[int] = set()
    hallucinated = 0
    for value in values or []:
        try:
            cid = int(str(value.get("corpusid") if isinstance(value, dict) else value).strip())
        except Exception:
            hallucinated += 1
            continue
        if cid not in allowed:
            hallucinated += 1
            continue
        if cid not in seen:
            ranked.append(cid)
            seen.add(cid)
    return ranked, hallucinated, meta


def build_needed_terms(queries: Iterable[tuple[str, list[str]]]) -> set[str]:
    terms: set[str] = set()
    for query, subqueries in queries:
        terms.update(tokenize(query))
        for subq in subqueries:
            terms.update(tokenize(subq))
    return terms


def prepare_queries(
    repo: RealScholarQueryCorpus,
    queries,
    gold_meta: dict[str, dict[str, Any]],
    report_dir: Path,
    dense_model: str,
    rerank_model: str,
    candidate_top_k: int,
    cross_top_n: int,
    dense_batch_size: int,
    dense_encode_chunk_size: int,
    rerank_batch_size: int,
    device: str,
    prompt_k: int,
    limit: int | None,
) -> tuple[list[PreparedQuery], dict[str, Any], dict[str, str]]:
    start = time.perf_counter()
    corpus = repo.load_corpus()
    corpus_ids = repo.corpus_ids
    docs = corpus["text"].tolist()
    if limit:
        queries = queries[:limit]

    raw_llm_dir = report_dir / "raw" / "llm"
    llm = LLMClient(raw_llm_dir, max_tokens=4096)
    precheck = llm.precheck()
    if not precheck.get("valid"):
        raise RuntimeError("LLM precheck failed; see reports/m060/raw/llm/precheck.json")
    decomposer = QueryDecomposer(llm)

    splits = deterministic_query_split([q.query_id for q in queries])
    write_json(report_dir / "split_protocol.json", {"method": "sha256(query_id) % 10 => 0-5 train, 6-7 holdout, 8-9 test", "splits": splits})

    decompositions: dict[str, list[str]] = {}
    decomp_rows: list[tuple[str, list[str]]] = []
    for q in queries:
        decomp = decomposer.decompose(q.query_id, q.query)
        subqueries = [s for s in decomp.subqueries if s.strip()] or [q.query]
        decompositions[q.query_id] = subqueries
        decomp_rows.append((q.query, subqueries))
        print(json.dumps({"decomposed": q.query_id, "subqueries": len(subqueries), "cached": bool(decomp.meta.get("cached"))}, ensure_ascii=False))

    needed_terms = build_needed_terms(decomp_rows)
    sparse = SparseQueryTermIndex(docs, needed_terms, cache_dir=report_dir / "cache")

    dense_start = time.perf_counter()
    dense = DenseV2Retriever(
        docs,
        report_dir / "cache" / "dense_v2",
        model_name=dense_model,
        batch_size=dense_batch_size,
        device=device,
        encode_chunk_size=dense_encode_chunk_size,
    )
    dense_load_encode_s = time.perf_counter() - dense_start
    reranker = CrossEncoderReranker(report_dir / "cache" / "rerank", model_name=rerank_model, batch_size=rerank_batch_size, device=device)

    pre_cfg = FusionV2Config(weights=PRE_RERANK_WEIGHTS, candidate_top_k=candidate_top_k, cross_top_n=cross_top_n)

    prepared: list[PreparedQuery] = []
    raw_query_dir = report_dir / "raw" / "query_records"
    raw_query_dir.mkdir(parents=True, exist_ok=True)
    for q in queries:
        q_start = time.perf_counter()
        subqueries = decompositions[q.query_id]
        keyword_scores = sparse.keyword_scores(q.query)
        bm25_scores = sparse.bm25_scores(q.query)
        dense_scores = dense.scores(q.query)
        sub_bm25_scores = max_or_zero([sparse.bm25_scores(subq) for subq in subqueries], len(corpus_ids))
        sub_dense_scores = max_or_zero([row for row in dense.batch_scores(subqueries)], len(corpus_ids))
        pool_ids = pool_from_sources([keyword_scores, bm25_scores, dense_scores, sub_bm25_scores, sub_dense_scores], corpus_ids, candidate_top_k)
        pool_indices = [repo.id_to_index[cid] for cid in pool_ids if cid in repo.id_to_index]
        base_features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25_scores, sub_dense_scores, {})
        pre_ranked = rank_with_features(pool_indices, corpus_ids, base_features, pre_cfg)
        cross_candidate_ids = [r.corpusid for r in pre_ranked[:cross_top_n]]
        cross_scores_by_id = reranker.score(q.query_id, q.query, cross_candidate_ids, corpus, repo.id_to_index)
        cross_scores_by_index = {repo.id_to_index[cid]: score for cid, score in cross_scores_by_id.items() if cid in repo.id_to_index}
        features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25_scores, sub_dense_scores, cross_scores_by_index)

        pre_scores = np.zeros(len(corpus_ids), dtype=np.float32)
        base_weights = pre_cfg.normalized_weights()
        base_w = np.array([base_weights[k] for k in FEATURES], dtype=np.float32)
        if pool_indices:
            pre_scores[np.array(pool_indices, dtype=np.int64)] = base_features @ base_w
        single_ranked, hallucinated, single_meta = single_llm_rank(llm, q.query_id, q.query, pool_ids, pool_indices, corpus, corpus_ids, pre_scores, prompt_k=prompt_k)

        baseline_rankings = {
            "keyword": score_ranking(keyword_scores, corpus_ids, pool_indices),
            "bm25": score_ranking(bm25_scores, corpus_ids, pool_indices),
            "neural_embedding_v2": score_ranking(dense_scores, corpus_ids, pool_indices),
            "single_llm": single_ranked,
        }
        elapsed_s = time.perf_counter() - q_start
        meta = gold_meta[q.query_id]
        record = PreparedQuery(
            query_id=q.query_id,
            query=q.query,
            split=splits[q.query_id],
            resolvable_gold=set(int(x) for x in meta["resolvable_gold"]),
            full_gold=set(int(x) for x in meta["full_gold"]),
            pool_ids=pool_ids,
            pool_indices=pool_indices,
            features=features,
            baseline_rankings=baseline_rankings,
            elapsed_s=elapsed_s,
            cross_candidate_count=len(cross_candidate_ids),
            decomposition=subqueries,
            single_llm_meta=single_meta,
            single_llm_hallucinated=hallucinated,
        )
        prepared.append(record)
        write_json(
            raw_query_dir / f"{q.query_id}.json",
            {
                "query_id": q.query_id,
                "split": splits[q.query_id],
                "resolvable_gold": sorted(record.resolvable_gold),
                "full_gold_count": len(record.full_gold),
                "pool_size": len(pool_ids),
                "pool_ids": pool_ids,
                "decomposition": subqueries,
                "cross_candidate_ids": cross_candidate_ids,
                "baseline_top20": {k: v[:20] for k, v in baseline_rankings.items()},
                "single_llm_hallucinated_or_out_of_pool": hallucinated,
                "elapsed_s": elapsed_s,
            },
        )
        print(json.dumps({"prepared": q.query_id, "split": splits[q.query_id], "pool": len(pool_ids), "elapsed_s": round(elapsed_s, 3)}, ensure_ascii=False))

    meta = {
        "precheck": precheck,
        "sparse": sparse.metadata(),
        "dense": dense.metadata(),
        "reranker": reranker.metadata(),
        "dense_load_or_encode_s": dense_load_encode_s,
        "prepare_total_s": time.perf_counter() - start,
        "candidate_top_k": candidate_top_k,
        "cross_top_n": cross_top_n,
        "prompt_k": prompt_k,
        "device": device,
        "query_count": len(prepared),
    }
    return prepared, meta, splits


def rows_for_records(records: list[PreparedQuery], corpus_ids: np.ndarray, final_cfg: FusionV2Config, no_rerank_cfg: FusionV2Config, scope: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    for record in records:
        gold = record.resolvable_gold if scope == "resolvable" else record.full_gold
        rankings = dict(record.baseline_rankings)
        rankings["scholarloop_a_v2_no_rerank"] = ranking_from_features(record.pool_indices, corpus_ids, record.features, no_rerank_cfg)
        final_ranked = rank_with_features(record.pool_indices, corpus_ids, record.features, final_cfg)
        rankings["scholarloop_a_v2"] = [r.corpusid for r in final_ranked]
        qrow: dict[str, Any] = {
            "scope": scope,
            "query_id": record.query_id,
            "split": record.split,
            "gold_count": len(gold),
            "pool_size": len(record.pool_ids),
            "decomposition": record.decomposition,
            "cross_candidate_count": record.cross_candidate_count,
            "elapsed_s": record.elapsed_s,
            "scholarloop_a_v2_reasons_top5": [r.__dict__ for r in final_ranked[:5]],
        }
        for system in SYSTEMS:
            ranked = rankings[system]
            met = metric_with_ndcg(ranked, gold)
            total_tokens = usage_tokens(record.single_llm_meta) if system == "single_llm" else 0
            latency_s = float(record.single_llm_meta.get("elapsed_s", 0.0) or 0.0) if system == "single_llm" else (record.elapsed_s if system == "scholarloop_a_v2" else 0.0)
            hallucinated = record.single_llm_hallucinated if system == "single_llm" else 0
            row = {
                "scope": scope,
                "query_id": record.query_id,
                "split": record.split,
                "system": system,
                **met,
                "hallucinated_or_out_of_pool": hallucinated,
                "total_tokens": total_tokens,
                "latency_s": latency_s,
            }
            rows.append(row)
            qrow[system] = {"ranked_top20": ranked[:20], **met, "hallucinated_or_out_of_pool": hallucinated}
        per_query.append(qrow)
    return rows, per_query


def tune_non_zero_shot(records: list[PreparedQuery], corpus_ids: np.ndarray) -> dict[str, Any]:
    train = [r for r in records if r.split == "train"]
    grid = candidate_weight_grid(include_cross=True)
    best_cfg = grid[0]
    best_f1 = -1.0
    start = time.perf_counter()
    for cfg in grid:
        vals: list[float] = []
        for record in train:
            ranked = ranking_from_features(record.pool_indices, corpus_ids, record.features, cfg)
            vals.append(metric_with_ndcg(ranked, record.resolvable_gold)["F1"])
        mean_f1 = float(statistics.mean(vals)) if vals else 0.0
        if mean_f1 > best_f1:
            best_f1 = mean_f1
            best_cfg = cfg
    by_split: dict[str, Any] = {}
    for split in ["train", "holdout", "test"]:
        selected = [r for r in records if r.split == split]
        vals = [metric_with_ndcg(ranking_from_features(r.pool_indices, corpus_ids, r.features, best_cfg), r.resolvable_gold) for r in selected]
        by_split[split] = {
            "queries": len(vals),
            "F1": float(statistics.mean(v["F1"] for v in vals)) if vals else 0.0,
            "P@10": float(statistics.mean(v["P@10"] for v in vals)) if vals else 0.0,
            "R@20": float(statistics.mean(v["R@20"] for v in vals)) if vals else 0.0,
            "NDCG@20": float(statistics.mean(v["NDCG@20"] for v in vals)) if vals else 0.0,
        }
    return {
        "label": "non_zero_shot_retuned_on_RealScholarQuery_train_only",
        "warning": "Exploratory only; not used for M060 zero-shot/generalization wall and must not be claimed as frozen transfer.",
        "grid_size": len(grid),
        "best_weights": best_cfg.normalized_weights(),
        "metrics_by_split": by_split,
        "elapsed_s": time.perf_counter() - start,
    }


def write_data_sources(report_dir: Path, audit: dict[str, Any], corpus_meta: dict[str, Any]) -> None:
    lines = [
        "# M060 data sources and dual-gold audit",
        "",
        "- Benchmark: RealScholarQuery/PaSa (official `RealScholarQuery/test.jsonl` + `paper_database/`).",
        "- Gold policy: official gold only; no self-labeling.",
        "- Reachability rule: arXiv id in `id2paper.json` OR normalized title in `cs_paper_2nd.zip`.",
        "- Primary metric: resolvable gold only.",
        "- Robustness metric: all 791 official gold, with unresolvable gold counting as equal misses for every system.",
        "",
        "## Counts",
        f"- Queries: `{audit['query_count']}`",
        f"- Official gold: `{audit['official_gold_count']}`",
        f"- Resolvable gold: `{audit['resolvable_gold_count']}` ({audit['resolvable_ratio']:.4f})",
        f"- Unresolvable gold: `{audit['unresolvable_gold_count']}` across `{audit['queries_with_unresolvable_gold_count']}` queries",
        f"- Corpus rows: `{corpus_meta.get('rows', 'n/a')}`",
        "",
        "## Unresolvable gold by query",
    ]
    for row in audit["per_query_unresolvable"]:
        lines.append(f"- `{row['query_id']}`: {row['unresolvable_count']} / {row['gold_count']}")
    lines += ["", "## 52 unresolvable official gold (not in official candidate pool)"]
    for item in audit["unresolvable_gold"]:
        lines.append(f"- `{item['query_id']}` #{item['ordinal']}: arxiv=`{item['arxiv_id']}` title={item['title']!r} reason=`{item['reason']}`")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "data-sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(report_dir: Path, result: dict[str, Any], sig: dict[str, Any]) -> None:
    res = {r["system"]: r for r in result["metrics"]["resolvable"]["aggregate"]}
    full = {r["system"]: r for r in result["metrics"]["full791"]["aggregate"]}
    primary = sig["resolvable"]["a_v2_vs_bm25_f1"]
    robust = sig["full791"]["a_v2_vs_bm25_f1"]
    lines = [
        "# M060 RealScholarQuery/PaSa frozen-transfer evaluation report",
        "",
        f"Status: `{result['status']}`",
        f"Wall passed: `{result['wall_passed']}`",
        "",
        "## Primary (resolvable gold)",
        f"- A-v2 F1: `{res['scholarloop_a_v2']['F1']:.6f}`",
        f"- BM25 F1: `{res['bm25']['F1']:.6f}`",
        f"- ΔF1 bootstrap: `{primary['bootstrap']['mean_delta']:.6f}`, CI95=`[{primary['bootstrap']['ci95'][0]:.6f}, {primary['bootstrap']['ci95'][1]:.6f}]`, passed=`{primary['bootstrap']['passed']}`",
        f"- ΔF1 permutation p(one-sided): `{primary['permutation']['p_one_sided']:.6f}`, passed=`{primary['permutation']['passed']}`",
        "",
        "## Robustness (full 791 official gold; 52 as equal misses)",
        f"- A-v2 F1: `{full['scholarloop_a_v2']['F1']:.6f}`",
        f"- BM25 F1: `{full['bm25']['F1']:.6f}`",
        f"- ΔF1 bootstrap: `{robust['bootstrap']['mean_delta']:.6f}`, CI95=`[{robust['bootstrap']['ci95'][0]:.6f}, {robust['bootstrap']['ci95'][1]:.6f}]`, passed=`{robust['bootstrap']['passed']}`",
        f"- ΔF1 permutation p(one-sided): `{robust['permutation']['p_one_sided']:.6f}`, passed=`{robust['permutation']['passed']}`",
        "",
        "## Aggregate table (resolvable)",
        "| system | P@10 | R@20 | F1 | NDCG@20 | hallucinated/out-of-pool |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for system in SYSTEMS:
        row = res[system]
        lines.append(f"| {system} | {row['P@10']:.4f} | {row['R@20']:.4f} | {row['F1']:.4f} | {row['NDCG@20']:.4f} | {row['hallucinated_or_out_of_pool']} |")
    if result.get("stop_reasons"):
        lines += ["", "## Stop reasons", *[f"- {r}" for r in result["stop_reasons"]]]
    (report_dir / "评测报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stop(report_dir: Path, result: dict[str, Any], sig: dict[str, Any] | None = None) -> None:
    reasons = "\n".join(f"- {r}" for r in result.get("stop_reasons", [])) or "- unspecified"
    text = f"""# M060 stop report

Status: `{result.get('status')}`

## Reasons
{reasons}

## Non-negotiables preserved
- No official gold was self-labeled or repaired.
- M040 A-v2 frozen configuration was not changed for the primary wall.
- Upstream M010-M050 artifacts remain read-only.
"""
    if sig:
        text += "\n## Significance snapshot\n```json\n" + json.dumps(sig, ensure_ascii=False, indent=2)[:4000] + "\n```\n"
    (report_dir / "STOP_REPORT.md").write_text(text, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    repo = RealScholarQueryCorpus(raw_root=Path(args.raw_root), cache_dir=report_dir / "cache" / "realscholarquery")
    repo.validate_raw_files()
    audit = repo.audit_gold()
    write_json(report_dir / "t0_probe.json", audit)

    stop_reasons: list[str] = []
    if audit["resolvable_ratio"] < 0.60:
        stop_reasons.append(f"resolvable gold ratio below 60%: {audit['resolvable_ratio']:.4f}")
    if audit.get("unexpected_unparseable_causes"):
        stop_reasons.append("unexpected gold unparseable causes: " + ", ".join(audit["unexpected_unparseable_causes"]))
    if stop_reasons:
        result = {"status": "blocked_t0_gold_audit", "wall_passed": False, "stop_reasons": stop_reasons, "gold_audit": audit}
        write_json(report_dir / "results.json", result)
        write_json(report_dir / "final_summary.json", {"status": result["status"], "stop_reasons": stop_reasons})
        write_stop(report_dir, result)
        return 2
    if args.audit_only:
        corpus_meta = repo.build_corpus_cache(force=False) if args.build_corpus_in_audit else {}
        write_data_sources(report_dir, audit, corpus_meta)
        write_json(report_dir / "final_summary.json", {"status": "audit_only_complete", "gold_audit": {k: audit[k] for k in ["query_count", "official_gold_count", "resolvable_gold_count", "unresolvable_gold_count", "queries_with_unresolvable_gold_count"]}})
        return 0

    queries, gold_meta, _audit2 = repo.load_queries()
    corpus_meta = repo.build_corpus_cache(force=args.force_corpus)
    write_data_sources(report_dir, audit, corpus_meta)

    m040 = read_json(Path("reports/m040/results.json"))
    m040_protocol = m040.get("protocol", {})
    expected_weights = m040_protocol.get("final_weights") or FROZEN_WEIGHTS
    if {k: round(float(v), 12) for k, v in expected_weights.items()} != {k: round(float(v), 12) for k, v in FROZEN_WEIGHTS.items()}:
        raise RuntimeError("M040 frozen final_weights differ from expected M060 contract")

    prepared, prep_meta, splits = prepare_queries(
        repo=repo,
        queries=queries,
        gold_meta=gold_meta,
        report_dir=report_dir,
        dense_model=args.dense_model,
        rerank_model=args.rerank_model,
        candidate_top_k=args.candidate_top_k,
        cross_top_n=args.cross_top_n,
        dense_batch_size=args.dense_batch_size,
        dense_encode_chunk_size=args.dense_encode_chunk_size,
        rerank_batch_size=args.rerank_batch_size,
        device=args.device,
        prompt_k=args.prompt_k,
        limit=args.limit,
    )
    corpus_ids = repo.corpus_ids
    final_cfg = FusionV2Config(weights=FROZEN_WEIGHTS, candidate_top_k=args.candidate_top_k, cross_top_n=args.cross_top_n)
    no_rerank_cfg = FusionV2Config(weights=NO_RERANK_WEIGHTS, candidate_top_k=args.candidate_top_k, cross_top_n=args.cross_top_n)

    resolvable_rows, resolvable_per_query = rows_for_records(prepared, corpus_ids, final_cfg, no_rerank_cfg, scope="resolvable")
    full_rows, full_per_query = rows_for_records(prepared, corpus_ids, final_cfg, no_rerank_cfg, scope="full791")
    all_rows = resolvable_rows + full_rows
    write_csv(report_dir / "results.csv", all_rows)
    with (report_dir / "per_query.jsonl").open("w", encoding="utf-8") as f:
        for row in resolvable_per_query + full_per_query:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    metrics = {
        "resolvable": {
            "scope": "resolvable official gold only",
            "aggregate": [aggregate(resolvable_rows, system) for system in SYSTEMS],
            "by_split": aggregate_by_split(resolvable_rows, splits),
            "per_query": resolvable_per_query,
        },
        "full791": {
            "scope": "all official gold; unresolvable gold count as equal misses for every system",
            "aggregate": [aggregate(full_rows, system) for system in SYSTEMS],
            "by_split": aggregate_by_split(full_rows, splits),
            "per_query": full_per_query,
        },
    }
    sig = {"resolvable": significance_for(resolvable_rows, args.bootstrap_n), "full791": significance_for(full_rows, args.bootstrap_n)}
    primary_pass = bool(sig["resolvable"]["a_v2_vs_bm25_f1"]["passed"])
    if not primary_pass:
        stop_reasons.append("M040 frozen A-v2 did not significantly beat BM25 on RealScholarQuery resolvable-gold F1")
    h5_violations = sum(r["hallucinated_or_out_of_pool"] for r in resolvable_rows if r["system"] == "scholarloop_a_v2")
    if h5_violations:
        stop_reasons.append(f"H5 violation: A-v2 out-of-pool/fabricated ids = {h5_violations}")

    retuned = tune_non_zero_shot(prepared, corpus_ids) if not primary_pass else None
    status = "implemented_pending_review" if not stop_reasons else "blocked_frozen_av2_not_significant"
    wall_passed = not stop_reasons
    result = {
        "status": status,
        "wall_passed": wall_passed,
        "stop_reasons": stop_reasons,
        "benchmark": "RealScholarQuery/PaSa",
        "query_count": len(prepared),
        "gold_audit": audit,
        "protocol": {
            "zero_shot_transfer": True,
            "m040_results_sha256": sha256_file(Path("reports/m040/results.json")),
            "frozen_final_weights": FROZEN_WEIGHTS,
            "no_rerank_weights": NO_RERANK_WEIGHTS,
            "dense_model": args.dense_model,
            "rerank_model": args.rerank_model,
            "candidate_top_k": args.candidate_top_k,
            "cross_top_n": args.cross_top_n,
            "single_llm_prompt_k": args.prompt_k,
            "shared_candidate_pool": "keyword/BM25/dense_v2/sub_bm25/sub_dense_v2 top-k union; all systems constrained to the same per-query pool",
            "temperature": 0,
            "seed": 42,
            "dual_gold_policy": audit["dual_verification_method"],
            "no_gold_self_labeling": True,
        },
        "preparation": prep_meta,
        "corpus_meta": corpus_meta,
        "metrics": metrics,
        "significance": sig,
        "non_zero_shot_retuned_control": retuned,
        "efficiency": {
            "total_wall_s": time.perf_counter() - start,
            "per_query_elapsed_s_mean": float(statistics.mean(r.elapsed_s for r in prepared)) if prepared else 0.0,
            "per_query_elapsed_s_p95": percentile([r.elapsed_s for r in prepared], 95),
        },
    }
    write_json(report_dir / "results.json", result)
    write_json(report_dir / "significance.json", sig)
    write_report(report_dir, result, sig)
    summary = {
        "status": status,
        "wall_passed": wall_passed,
        "query_count": len(prepared),
        "official_gold_count": audit["official_gold_count"],
        "resolvable_gold_count": audit["resolvable_gold_count"],
        "unresolvable_gold_count": audit["unresolvable_gold_count"],
        "primary_delta_f1": sig["resolvable"]["a_v2_vs_bm25_f1"]["bootstrap"]["mean_delta"],
        "primary_passed": primary_pass,
        "stop_reasons": stop_reasons,
    }
    write_json(report_dir / "final_summary.json", summary)
    if stop_reasons:
        write_stop(report_dir, result, sig)
        return 2
    stop_path = report_dir / "STOP_REPORT.md"
    if stop_path.exists():
        stop_path.unlink()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M060 RealScholarQuery/PaSa frozen A-v2 cross-benchmark evaluation")
    parser.add_argument("--report-dir", default="reports/m060")
    parser.add_argument("--raw-root", default="reports/m060/raw/pasa-dataset")
    parser.add_argument("--dense-model", default=DEFAULT_DENSE_V2_MODEL)
    parser.add_argument("--rerank-model", default=DEFAULT_RERANK_MODEL)
    parser.add_argument("--candidate-top-k", type=int, default=100)
    parser.add_argument("--cross-top-n", type=int, default=50)
    parser.add_argument("--prompt-k", type=int, default=12)
    parser.add_argument("--dense-batch-size", type=int, default=64)
    parser.add_argument("--dense-encode-chunk-size", type=int, default=4096)
    parser.add_argument("--rerank-batch-size", type=int, default=32)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--bootstrap-n", type=int, default=10000)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force-corpus", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--build-corpus-in-audit", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))

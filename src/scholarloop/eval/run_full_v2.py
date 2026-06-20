from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

import scholarloop.config as config  # noqa: F401 - import triggers approved credential self-load
from scholarloop.corpus import LitSearchCorpus, QueryRecord
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
from scholarloop.retrieval.bm25 import BM25Retriever
from scholarloop.retrieval.dense_v2 import DEFAULT_DENSE_V2_MODEL, DenseV2Retriever
from scholarloop.utils import normalize_values, percentile, read_json, score_ranking, top_ids_from_scores, write_json


SYSTEMS = [
    "keyword",
    "bm25",
    "neural_embedding_v2",
    "single_llm_frozen_m010",
    "scholarloop_a_v1_frozen",
    "scholarloop_a_v2_no_rerank",
    "scholarloop_a_v2",
]


@dataclass
class PreparedQuery:
    query_id: str
    query: str
    split: str
    gold: set[int]
    pool_ids: list[int]
    pool_indices: list[int]
    features: np.ndarray
    baseline_rankings: dict[str, list[int]]
    elapsed_s: float
    cross_candidate_count: int
    decomposition: list[str]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def aggregate(rows: list[dict[str, Any]], system: str) -> dict[str, Any]:
    subset = [r for r in rows if r["system"] == system]
    out: dict[str, Any] = {"system": system, "queries": len(subset)}
    for m in ["P@10", "R@20", "F1", "NDCG@20"]:
        out[m] = float(statistics.mean([r[m] for r in subset])) if subset else 0.0
    out["hallucinated_or_out_of_pool"] = int(sum(r.get("hallucinated_or_out_of_pool", 0) for r in subset))
    out["total_tokens"] = int(sum(r.get("total_tokens", 0) for r in subset))
    out["total_latency_s"] = float(sum(r.get("latency_s", 0.0) for r in subset))
    return out


def aggregate_by_split(rows: list[dict[str, Any]], splits: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for split in ["train", "holdout", "test"]:
        split_rows = [r for r in rows if splits.get(r["query_id"]) == split]
        out[split] = [aggregate(split_rows, s) for s in SYSTEMS]
    return out


def paired_bootstrap(a: list[float], b: list[float], n: int = 10000, seed: int = 42) -> dict[str, Any]:
    diffs = np.array(a, dtype=np.float64) - np.array(b, dtype=np.float64)
    rng = np.random.default_rng(seed)
    if len(diffs) == 0:
        return {"mean_delta": 0.0, "ci95": [0.0, 0.0], "resamples": n, "passed": False}
    samples = rng.choice(diffs, size=(n, len(diffs)), replace=True).mean(axis=1)
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return {
        "mean_delta": float(diffs.mean()),
        "ci95": [float(lo), float(hi)],
        "resamples": n,
        "passed": bool(lo > 0),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "query_id",
        "split",
        "system",
        "P@10",
        "R@20",
        "F1",
        "NDCG@20",
        "hallucinated_or_out_of_pool",
        "total_tokens",
        "latency_s",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_m010_frozen(report_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    m010 = read_json(Path("reports/m010/results.json"))
    by_query = {q["query_id"]: q for q in m010["per_query"]}
    csv_rows: dict[str, dict[str, dict[str, Any]]] = {}
    csv_path = Path("reports/m010/results.csv")
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                csv_rows.setdefault(row["query_id"], {})[row["system"]] = row
    agg = {r["system"]: r for r in m010["aggregate"]}
    a_v1 = float(agg["scholarloop_a"]["F1"])
    if round(a_v1, 4) != 0.1128:
        raise RuntimeError(f"M010 frozen A-v1 F1 mismatch: expected rounded 0.1128, got {a_v1}")
    write_json(
        report_dir / "baseline_snapshot.json",
        {
            "m010_status": m010.get("status"),
            "query_count": m010.get("query_count"),
            "a_v1_f1_exact": a_v1,
            "a_v1_f1_rounded_4": round(a_v1, 4),
            "bm25_f1_exact": float(agg["bm25"]["F1"]),
            "m010_results_sha256": sha256_file(Path("reports/m010/results.json")),
            "m010_significance_sha256": sha256_file(Path("reports/m010/significance.json")),
            "config_present": getattr(config, "PRESENT", {}),
        },
    )
    return m010, by_query, csv_rows


def max_or_zero(arrays: list[np.ndarray], length: int) -> np.ndarray:
    if not arrays:
        return np.zeros(length, dtype=np.float32)
    return np.max(np.vstack(arrays), axis=0).astype(np.float32)


def pool_from_sources(scores: list[np.ndarray], corpus_ids: np.ndarray, top_k: int) -> list[int]:
    pool: set[int] = set()
    for score in scores:
        pool.update(top_ids_from_scores(score, corpus_ids, top_k))
    return sorted(pool)


def ranking_from_features_fast(record: PreparedQuery, corpus_ids: np.ndarray, config: FusionV2Config) -> list[int]:
    weights = config.normalized_weights()
    w = np.array([weights[k] for k in FEATURES], dtype=np.float32)
    scores = record.features @ w
    ids = corpus_ids[np.array(record.pool_indices, dtype=np.int64)]
    order = np.lexsort((ids, -scores))
    return [int(ids[i]) for i in order[: config.final_k]]


def evaluate_config(records: list[PreparedQuery], corpus_ids: np.ndarray, config: FusionV2Config, split: str | None = None) -> dict[str, float]:
    selected = [r for r in records if split is None or r.split == split]
    if not selected:
        return {"queries": 0, "F1": 0.0, "NDCG@20": 0.0, "P@10": 0.0, "R@20": 0.0}
    metrics = []
    for record in selected:
        ranked = ranking_from_features_fast(record, corpus_ids, config)
        metrics.append(metric_with_ndcg(ranked, record.gold))
    return {
        "queries": len(selected),
        "F1": float(statistics.mean(m["F1"] for m in metrics)),
        "NDCG@20": float(statistics.mean(m["NDCG@20"] for m in metrics)),
        "P@10": float(statistics.mean(m["P@10"] for m in metrics)),
        "R@20": float(statistics.mean(m["R@20"] for m in metrics)),
    }


def tune_config(records: list[PreparedQuery], corpus_ids: np.ndarray, include_cross: bool) -> tuple[FusionV2Config, dict[str, Any]]:
    grid = candidate_weight_grid(include_cross=include_cross)
    best_cfg = grid[0]
    best_metrics = {"F1": -1.0, "NDCG@20": -1.0, "P@10": -1.0, "R@20": -1.0, "queries": 0}
    start = time.perf_counter()
    for cfg in grid:
        metrics = evaluate_config(records, corpus_ids, cfg, split="train")
        key = (
            metrics["F1"],
            metrics["NDCG@20"],
            metrics["P@10"],
            cfg.normalized_weights()["dense_v2"],
            cfg.normalized_weights()["cross_encoder"],
            -cfg.normalized_weights()["bm25"],
        )
        best_key = (
            best_metrics["F1"],
            best_metrics["NDCG@20"],
            best_metrics["P@10"],
            best_cfg.normalized_weights()["dense_v2"],
            best_cfg.normalized_weights()["cross_encoder"],
            -best_cfg.normalized_weights()["bm25"],
        )
        if key > best_key:
            best_cfg = cfg
            best_metrics = metrics
    protocol = {
        "include_cross": include_cross,
        "grid_size": len(grid),
        "tuned_on": "train only",
        "selection_metric": "mean F1; tie-break NDCG@20/P@10/dense/cross/less-bm25, no holdout/test peeking",
        "elapsed_s": time.perf_counter() - start,
        "best_weights": best_cfg.normalized_weights(),
        "train_metrics": best_metrics,
        "holdout_metrics": evaluate_config(records, corpus_ids, best_cfg, split="holdout"),
        "test_metrics": evaluate_config(records, corpus_ids, best_cfg, split="test"),
    }
    return best_cfg, protocol


def prepare_queries(
    repo: LitSearchCorpus,
    queries: list[QueryRecord],
    m010_by_query: dict[str, dict[str, Any]],
    report_dir: Path,
    dense_model: str,
    rerank_model: str,
    candidate_top_k: int,
    cross_top_n: int,
    dense_batch_size: int,
    rerank_batch_size: int,
    device: str,
    limit: int | None = None,
) -> tuple[list[PreparedQuery], dict[str, Any]]:
    start = time.perf_counter()
    corpus = repo.load_corpus()
    corpus_ids = repo.corpus_ids
    docs = corpus["text"].tolist()
    if limit:
        queries = queries[:limit]
    bm25 = BM25Retriever(docs)
    dense_start = time.perf_counter()
    dense = DenseV2Retriever(
        docs,
        report_dir / "cache" / "dense_v2",
        model_name=dense_model,
        batch_size=dense_batch_size,
        device=device,
    )
    dense_load_encode_s = time.perf_counter() - dense_start
    reranker = CrossEncoderReranker(
        report_dir / "cache" / "rerank",
        model_name=rerank_model,
        batch_size=rerank_batch_size,
        device=device,
    )
    splits = deterministic_query_split([q.query_id for q in queries])
    write_json(report_dir / "split_protocol.json", {"method": "sha256(query_id) % 10 => 0-5 train, 6-7 holdout, 8-9 test", "splits": splits})

    prepared: list[PreparedQuery] = []
    raw_dir = report_dir / "raw" / "query_records"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for q in queries:
        q_start = time.perf_counter()
        m010_q = m010_by_query[q.query_id]
        decomposition = [str(x) for x in m010_q.get("decomposition", []) if str(x).strip()] or [q.query]
        keyword_scores = bm25.keyword_scores(q.query)
        bm25_scores = bm25.bm25_scores(q.query)
        dense_scores = dense.scores(q.query)
        sub_bm25_scores = max_or_zero([bm25.bm25_scores(subq) for subq in decomposition], len(corpus_ids))
        sub_dense_scores = max_or_zero([row for row in dense.batch_scores(decomposition)], len(corpus_ids))
        pool_ids = pool_from_sources(
            [keyword_scores, bm25_scores, dense_scores, sub_bm25_scores, sub_dense_scores],
            corpus_ids,
            candidate_top_k,
        )
        pool_indices = [repo.id_to_index[cid] for cid in pool_ids]
        base_features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25_scores, sub_dense_scores, {})
        pre_cfg = FusionV2Config(
            weights={"bm25": 0.25, "dense_v2": 0.55, "sub_bm25": 0.10, "sub_dense_v2": 0.10, "cross_encoder": 0.0},
            candidate_top_k=candidate_top_k,
            cross_top_n=cross_top_n,
        )
        pre_ranked = rank_with_features(pool_indices, corpus_ids, base_features, pre_cfg)
        cross_candidate_ids = [r.corpusid for r in pre_ranked[:cross_top_n]]
        cross_scores_by_id = reranker.score(q.query_id, q.query, cross_candidate_ids, corpus, repo.id_to_index)
        cross_scores_by_index = {repo.id_to_index[cid]: score for cid, score in cross_scores_by_id.items() if cid in repo.id_to_index}
        features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25_scores, sub_dense_scores, cross_scores_by_index)
        baseline_rankings = {
            "keyword": score_ranking(keyword_scores, corpus_ids, pool_indices),
            "bm25": score_ranking(bm25_scores, corpus_ids, pool_indices),
            "neural_embedding_v2": score_ranking(dense_scores, corpus_ids, pool_indices),
            "single_llm_frozen_m010": [int(x) for x in m010_q["single_llm"]["ranked_top20"]],
            "scholarloop_a_v1_frozen": [int(x) for x in m010_q["scholarloop_a"]["ranked_top20"]],
        }
        elapsed_s = time.perf_counter() - q_start
        record = PreparedQuery(
            query_id=q.query_id,
            query=q.query,
            split=splits[q.query_id],
            gold=set(int(x) for x in q.gold),
            pool_ids=pool_ids,
            pool_indices=pool_indices,
            features=features,
            baseline_rankings=baseline_rankings,
            elapsed_s=elapsed_s,
            cross_candidate_count=len(cross_candidate_ids),
            decomposition=decomposition,
        )
        prepared.append(record)
        write_json(
            raw_dir / f"{q.query_id}.json",
            {
                "query_id": q.query_id,
                "split": splits[q.query_id],
                "gold": list(record.gold),
                "pool_size": len(pool_ids),
                "pool_ids": pool_ids,
                "decomposition_from_m010": decomposition,
                "cross_candidate_ids": cross_candidate_ids,
                "baseline_top20": {k: v[:20] for k, v in baseline_rankings.items()},
                "elapsed_s": elapsed_s,
            },
        )
        print(json.dumps({"prepared": q.query_id, "split": splits[q.query_id], "pool": len(pool_ids), "elapsed_s": round(elapsed_s, 3)}, ensure_ascii=False))

    meta = {
        "dense": dense.metadata(),
        "reranker": reranker.metadata(),
        "dense_load_or_encode_s": dense_load_encode_s,
        "prepare_total_s": time.perf_counter() - start,
        "candidate_top_k": candidate_top_k,
        "cross_top_n": cross_top_n,
        "device": device,
        "query_count": len(prepared),
    }
    return prepared, meta


def rows_for_records(
    records: list[PreparedQuery],
    corpus_ids: np.ndarray,
    final_cfg: FusionV2Config,
    no_rerank_cfg: FusionV2Config,
    m010_csv_rows: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    for record in records:
        q_record: dict[str, Any] = {
            "query_id": record.query_id,
            "split": record.split,
            "gold": sorted(record.gold),
            "pool_size": len(record.pool_ids),
            "decomposition_from_m010": record.decomposition,
            "cross_candidate_count": record.cross_candidate_count,
            "elapsed_s": record.elapsed_s,
        }
        rankings = dict(record.baseline_rankings)
        no_rerank = ranking_from_features_fast(record, corpus_ids, no_rerank_cfg)
        final_ranked = rank_with_features(record.pool_indices, corpus_ids, record.features, final_cfg)
        rankings["scholarloop_a_v2_no_rerank"] = no_rerank
        rankings["scholarloop_a_v2"] = [r.corpusid for r in final_ranked]
        q_record["scholarloop_a_v2_reasons_top5"] = [r.__dict__ for r in final_ranked[:5]]
        for system in SYSTEMS:
            ranked = rankings[system]
            met = metric_with_ndcg(ranked, record.gold)
            frozen = m010_csv_rows.get(record.query_id, {}).get(
                "single_llm" if system == "single_llm_frozen_m010" else "scholarloop_a" if system == "scholarloop_a_v1_frozen" else system,
                {},
            )
            total_tokens = int(float(frozen.get("total_tokens", 0) or 0))
            latency_s = float(frozen.get("latency_s", 0.0) or 0.0)
            if system.startswith("scholarloop_a_v2") or system in {"keyword", "bm25", "neural_embedding_v2"}:
                total_tokens = 0
                latency_s = record.elapsed_s if system == "scholarloop_a_v2" else 0.0
            row = {
                "query_id": record.query_id,
                "split": record.split,
                "system": system,
                **met,
                "hallucinated_or_out_of_pool": 0,
                "total_tokens": total_tokens,
                "latency_s": latency_s,
            }
            rows.append(row)
            q_record[system] = {"ranked_top20": ranked[:20], **met}
        per_query.append(q_record)
    return rows, per_query


def split_delta(split_aggs: dict[str, list[dict[str, Any]]], left: str, right: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for split, aggs in split_aggs.items():
        by = {r["system"]: r for r in aggs}
        out[split] = float(by[left]["F1"] - by[right]["F1"])
    return out


def write_report(path: Path, result: dict[str, Any], sig: dict[str, Any]) -> None:
    lines = [
        "# M040 A-v2 evaluation report",
        "",
        f"- Status: **{result['status']}**",
        f"- Query count: `{result['query_count']}`",
        f"- Dense model: `{result['protocol']['dense_model']}`",
        f"- Reranker: `{result['protocol']['rerank_model']}`",
        f"- Device: `{result['protocol']['device']}`",
        f"- Final weights: `{json.dumps(result['protocol']['final_weights'], ensure_ascii=False)}`",
        "",
        "## Aggregate metrics",
        "| system | P@10 | R@20 | F1 | NDCG@20 | hallucinated | tokens | latency_s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["aggregate"]:
        lines.append(
            f"| {r['system']} | {r['P@10']:.4f} | {r['R@20']:.4f} | {r['F1']:.4f} | {r['NDCG@20']:.4f} | "
            f"{r['hallucinated_or_out_of_pool']} | {r['total_tokens']} | {r['total_latency_s']:.2f} |"
        )
    lines += [
        "",
        "## Split F1 (anti-overfit evidence)",
        "| split | BM25 | A-v1 frozen | A-v2 | Δ(A-v2-BM25) | Δ(A-v2-A-v1) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split in ["train", "holdout", "test"]:
        by = {r["system"]: r for r in result["aggregate_by_split"][split]}
        lines.append(
            f"| {split} | {by['bm25']['F1']:.4f} | {by['scholarloop_a_v1_frozen']['F1']:.4f} | "
            f"{by['scholarloop_a_v2']['F1']:.4f} | {by['scholarloop_a_v2']['F1']-by['bm25']['F1']:.4f} | "
            f"{by['scholarloop_a_v2']['F1']-by['scholarloop_a_v1_frozen']['F1']:.4f} |"
        )
    lines += [
        "",
        "## Significance",
        f"- A-v2 vs BM25 ΔF1: `{sig['a_v2_vs_bm25_f1']['mean_delta']:.6f}`, "
        f"CI95=`[{sig['a_v2_vs_bm25_f1']['ci95'][0]:.6f}, {sig['a_v2_vs_bm25_f1']['ci95'][1]:.6f}]`, "
        f"passed=`{sig['a_v2_vs_bm25_f1']['passed']}`",
        f"- A-v2 vs A-v1 ΔF1: `{sig['a_v2_vs_a_v1_f1']['mean_delta']:.6f}`, "
        f"CI95=`[{sig['a_v2_vs_a_v1_f1']['ci95'][0]:.6f}, {sig['a_v2_vs_a_v1_f1']['ci95'][1]:.6f}]`, "
        f"passed=`{sig['a_v2_vs_a_v1_f1']['passed']}`",
        "",
        "## Efficiency",
        f"- Total wall seconds: `{result['efficiency']['total_wall_s']:.2f}`",
        f"- P50/P95 query seconds: `{result['efficiency']['p50_query_s']:.2f}` / `{result['efficiency']['p95_query_s']:.2f}`",
        f"- A-v2 API calls per query / tokens: `{result['efficiency']['a_v2_api_calls_per_query']}` / `{result['efficiency']['a_v2_total_tokens']}`",
        "",
        "## Stop condition",
        f"- Wall passed: `{result['wall_passed']}`",
    ]
    if result.get("stop_reasons"):
        for reason in result["stop_reasons"]:
            lines.append(f"- {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stop(path: Path, result: dict[str, Any], sig: dict[str, Any]) -> None:
    reasons = "\n".join(f"- {r}" for r in result.get("stop_reasons", []))
    text = f"""# M040 stop report - A-v2 gate not passed

- Status: BLOCKED
- Query count: {result['query_count']}
- A-v2 F1: {result['by_system']['scholarloop_a_v2']['F1']:.6f}
- BM25 F1: {result['by_system']['bm25']['F1']:.6f}
- A-v1 frozen F1: {result['by_system']['scholarloop_a_v1_frozen']['F1']:.6f}
- A-v2 vs BM25 CI95: [{sig['a_v2_vs_bm25_f1']['ci95'][0]:.6f}, {sig['a_v2_vs_bm25_f1']['ci95'][1]:.6f}]
- A-v2 vs A-v1 CI95: [{sig['a_v2_vs_a_v1_f1']['ci95'][0]:.6f}, {sig['a_v2_vs_a_v1_f1']['ci95'][1]:.6f}]

## Mandatory stop reasons
{reasons}

Per 040 §8/§10/§11, no criteria were changed, no samples were cherry-picked, and A-v1/M010 remained frozen.
"""
    path.write_text(text, encoding="utf-8")


def evaluate(
    report_dir: Path,
    bootstrap_n: int = 10000,
    candidate_top_k: int = 100,
    cross_top_n: int = 60,
    dense_model: str = DEFAULT_DENSE_V2_MODEL,
    rerank_model: str = DEFAULT_RERANK_MODEL,
    dense_batch_size: int = 64,
    rerank_batch_size: int = 32,
    device: str = "cpu",
    limit: int | None = None,
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "raw").mkdir(parents=True, exist_ok=True)
    (report_dir / "cache").mkdir(parents=True, exist_ok=True)
    start_total = time.perf_counter()
    m010, m010_by_query, m010_csv_rows = load_m010_frozen(report_dir)
    repo = LitSearchCorpus(Path("."))
    repo.validate_gold()
    queries = repo.load_queries()
    if limit:
        queries = queries[:limit]
    records, prep_meta = prepare_queries(
        repo,
        queries,
        m010_by_query,
        report_dir,
        dense_model=dense_model,
        rerank_model=rerank_model,
        candidate_top_k=candidate_top_k,
        cross_top_n=cross_top_n,
        dense_batch_size=dense_batch_size,
        rerank_batch_size=rerank_batch_size,
        device=device,
        limit=None,
    )
    corpus_ids = repo.corpus_ids
    final_cfg, tuning_protocol = tune_config(records, corpus_ids, include_cross=True)
    no_rerank_cfg, no_rerank_protocol = tune_config(records, corpus_ids, include_cross=False)
    rows, per_query = rows_for_records(records, corpus_ids, final_cfg, no_rerank_cfg, m010_csv_rows)
    aggregates = [aggregate(rows, s) for s in SYSTEMS]
    by_system = {r["system"]: r for r in aggregates}
    splits = {r.query_id: r.split for r in records}
    split_aggs = aggregate_by_split(rows, splits)

    def f1(system: str) -> list[float]:
        return [float(r["F1"]) for r in rows if r["system"] == system]

    sig = {
        "a_v2_vs_bm25_f1": paired_bootstrap(f1("scholarloop_a_v2"), f1("bm25"), n=bootstrap_n),
        "a_v2_vs_a_v1_f1": paired_bootstrap(f1("scholarloop_a_v2"), f1("scholarloop_a_v1_frozen"), n=bootstrap_n),
        "a_v2_vs_no_rerank_f1": paired_bootstrap(f1("scholarloop_a_v2"), f1("scholarloop_a_v2_no_rerank"), n=bootstrap_n),
        "bootstrap_n": bootstrap_n,
    }
    delta_vs_bm25_by_split = split_delta(split_aggs, "scholarloop_a_v2", "bm25")
    delta_vs_a1_by_split = split_delta(split_aggs, "scholarloop_a_v2", "scholarloop_a_v1_frozen")
    stop_reasons: list[str] = []
    if not sig["a_v2_vs_bm25_f1"]["passed"]:
        stop_reasons.append("A-v2 F1 was not paired-significantly above BM25 on the full LitSearch set.")
    if not (by_system["scholarloop_a_v2"]["F1"] > by_system["scholarloop_a_v1_frozen"]["F1"]):
        stop_reasons.append("A-v2 F1 did not exceed frozen A-v1 F1=0.1128.")
    for split in ["holdout", "test"]:
        if delta_vs_a1_by_split[split] <= 0:
            stop_reasons.append(f"A-v2 gain over A-v1 did not hold on {split} split.")
        if delta_vs_bm25_by_split[split] <= 0:
            stop_reasons.append(f"A-v2 gain over BM25 did not hold on {split} split.")
    hallucinated = int(sum(r.get("hallucinated_or_out_of_pool", 0) for r in rows if r["system"] == "scholarloop_a_v2"))
    if hallucinated != 0:
        stop_reasons.append("H5 hallucinated/out-of-pool count for A-v2 was non-zero.")

    latencies = [r.elapsed_s for r in records]
    status = "PASS" if not stop_reasons else "BLOCKED"
    result = {
        "status": status,
        "wall_passed": status == "PASS",
        "stop_reasons": stop_reasons,
        "query_count": len(records),
        "protocol": {
            "candidate_top_k": candidate_top_k,
            "cross_top_n": cross_top_n,
            "shared_candidate_pool": "keyword/BM25/dense_v2/sub_bm25/sub_dense_v2 top-k union; all M040 non-frozen systems constrained to this pool; A-v1 and single-LLM are frozen M010 comparators",
            "dense_model": dense_model,
            "rerank_model": rerank_model,
            "device": device,
            "temperature": 0,
            "seed": 42,
            "split": "sha256(query_id) % 10: 0-5 train, 6-7 holdout, 8-9 test; tune train only, report holdout/test",
            "final_weights": final_cfg.normalized_weights(),
            "no_rerank_weights": no_rerank_cfg.normalized_weights(),
            "h5": "A-v2 ranks only corpus IDs from LitSearch candidate pool; no generated paper IDs",
            "a_v1_frozen_f1": float(next(r for r in m010["aggregate"] if r["system"] == "scholarloop_a")["F1"]),
        },
        "model_metadata": prep_meta,
        "tuning": {"with_rerank": tuning_protocol, "without_rerank": no_rerank_protocol},
        "aggregate": aggregates,
        "by_system": by_system,
        "aggregate_by_split": split_aggs,
        "split_deltas": {"a_v2_vs_bm25": delta_vs_bm25_by_split, "a_v2_vs_a_v1": delta_vs_a1_by_split},
        "per_query": per_query,
        "hallucinated_or_out_of_pool": hallucinated,
        "efficiency": {
            "total_wall_s": time.perf_counter() - start_total,
            "prepare_total_s": prep_meta["prepare_total_s"],
            "dense_load_or_encode_s": prep_meta["dense_load_or_encode_s"],
            "p50_query_s": percentile(latencies, 50),
            "p95_query_s": percentile(latencies, 95),
            "a_v2_total_tokens": 0,
            "a_v2_avg_tokens_per_query": 0.0,
            "a_v2_api_calls_per_query": 0.0,
        },
    }
    write_json(report_dir / "results.json", result)
    write_csv(report_dir / "results.csv", rows)
    write_json(report_dir / "significance.json", sig | {"passed": status == "PASS", "stop_reasons": stop_reasons})
    write_report(report_dir / "A-v2评测报告.md", result, sig)
    if status != "PASS":
        write_stop(report_dir / "040-stop-report.md", result, sig)
    return {"status": status, "query_count": len(records), "report_dir": str(report_dir), "stop_reasons": stop_reasons}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default="reports/m040")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--candidate-top-k", type=int, default=100)
    parser.add_argument("--cross-top-n", type=int, default=60)
    parser.add_argument("--dense-model", default=DEFAULT_DENSE_V2_MODEL)
    parser.add_argument("--rerank-model", default=DEFAULT_RERANK_MODEL)
    parser.add_argument("--dense-batch-size", type=int, default=64)
    parser.add_argument("--rerank-batch-size", type=int, default=32)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    out = evaluate(
        report_dir=Path(args.report_dir),
        bootstrap_n=args.bootstrap,
        candidate_top_k=args.candidate_top_k,
        cross_top_n=args.cross_top_n,
        dense_model=args.dense_model,
        rerank_model=args.rerank_model,
        dense_batch_size=args.dense_batch_size,
        rerank_batch_size=args.rerank_batch_size,
        device=args.device,
        limit=args.limit,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["status"] == "PASS" else 5


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from scholarloop.pipeline import ScholarLoopPipeline
from scholarloop.utils import metric_for_ranking, normalize_values, percentile, score_ranking, write_json


def aggregate(rows: list[dict[str, Any]], system: str) -> dict[str, Any]:
    subset = [r for r in rows if r["system"] == system]
    out = {"system": system, "queries": len(subset)}
    for m in ["P@10", "R@20", "F1"]:
        out[m] = float(statistics.mean([r[m] for r in subset])) if subset else 0.0
    out["hallucinated_or_out_of_pool"] = int(sum(r.get("hallucinated_or_out_of_pool", 0) for r in subset))
    out["total_tokens"] = int(sum(r.get("total_tokens", 0) for r in subset))
    out["total_latency_s"] = float(sum(r.get("latency_s", 0.0) for r in subset))
    return out


def usage_tokens(meta: dict[str, Any]) -> int:
    usage = meta.get("usage") or {}
    for key in ["total_tokens", "totalTokenCount", "total"]:
        if usage.get(key) is not None:
            return int(usage[key])
    return 0


def paired_bootstrap(a: list[float], b: list[float], n: int = 10000, seed: int = 42) -> dict[str, Any]:
    diffs = np.array(a, dtype=np.float64) - np.array(b, dtype=np.float64)
    rng = np.random.default_rng(seed)
    if len(diffs) == 0:
        return {"mean_delta": 0.0, "ci95": [0.0, 0.0], "resamples": n, "passed": False}
    samples = rng.choice(diffs, size=(n, len(diffs)), replace=True).mean(axis=1)
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return {"mean_delta": float(diffs.mean()), "ci95": [float(lo), float(hi)], "resamples": n, "passed": bool(lo > 0)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["query_id", "system", "P@10", "R@20", "F1", "hallucinated_or_out_of_pool", "total_tokens", "latency_s"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def _progress_path(report_dir: Path, query_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in query_id)
    return report_dir / "progress" / f"{safe}.json"


def _load_query_progress(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["rows"], data["per_query"], data.get("reason_example")


def evaluate(limit: int | None, bootstrap_n: int, report_dir: Path, top_k: int = 100, max_new: int | None = None) -> dict[str, Any]:
    start_total = time.perf_counter()
    pipe = ScholarLoopPipeline(report_dir=report_dir, top_k=top_k)
    precheck = pipe.llm.precheck()
    if not precheck.get("valid"):
        raise RuntimeError("LLM precheck failed; see reports/m010/raw/llm/precheck.json")
    queries = pipe.repo.load_queries()
    if limit:
        queries = queries[:limit]
    rows: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    reason_examples: list[dict[str, Any]] = []
    processed_new = 0
    pending_queries = []
    for q in queries:
        if _progress_path(report_dir, q.query_id).exists():
            continue
        if max_new is not None and len(pending_queries) >= max_new:
            continue
        pending_queries.append(q)
    dense_scores_by_query_id: dict[str, np.ndarray] = {}
    if pending_queries:
        dense_batch = pipe.dense.batch_scores([q.query for q in pending_queries])
        dense_scores_by_query_id = {q.query_id: dense_batch[i] for i, q in enumerate(pending_queries)}

    for q in queries:
        progress = _progress_path(report_dir, q.query_id)
        if progress.exists():
            saved_rows, saved_q_record, saved_reason = _load_query_progress(progress)
            rows.extend(saved_rows)
            per_query.append(saved_q_record)
            if saved_reason and len(reason_examples) < 12:
                reason_examples.append(saved_reason)
            continue

        if max_new is not None and processed_new >= max_new:
            continue

        q_start = time.perf_counter()
        scores = {
            "keyword": pipe.bm25.keyword_scores(q.query),
            "bm25": pipe.bm25.bm25_scores(q.query),
            "neural_embedding": dense_scores_by_query_id[q.query_id],
        }
        pool = pipe.candidate_pool(scores)
        pool_indices = [pipe.repo.id_to_index[cid] for cid in pool]
        rankings = {name: score_ranking(score, pipe.corpus_ids, pool_indices) for name, score in scores.items()}
        combined = np.zeros(len(pipe.corpus_ids), dtype=np.float32)
        for score in scores.values():
            vals = normalize_values(score[pool_indices])
            for local, idx in enumerate(pool_indices):
                combined[idx] += vals[local]
        single_ranked, hallucinated, single_meta = pipe.single_llm_rank(q.query_id, q.query, pool, combined)
        ranked_results, decomp_meta = pipe.scholarloop_rank(q, pool, scores)
        rankings["single_llm"] = single_ranked
        rankings["scholarloop_a"] = [r.corpusid for r in ranked_results]
        gold = set(q.gold)
        q_record = {"query_id": q.query_id, "gold": list(q.gold), "pool_size": len(pool), "decomposition": decomp_meta.get("subqueries", [])}
        query_rows: list[dict[str, Any]] = []
        for system, ranked in rankings.items():
            met = metric_for_ranking(ranked, gold)
            meta = single_meta if system == "single_llm" else decomp_meta.get("meta", {}) if system == "scholarloop_a" else {}
            row = {
                "query_id": q.query_id, "system": system, **met,
                "hallucinated_or_out_of_pool": hallucinated if system == "single_llm" else 0,
                "total_tokens": usage_tokens(meta),
                "latency_s": float(meta.get("elapsed_s", 0.0) or 0.0),
            }
            rows.append(row)
            query_rows.append(row)
            q_record[system] = {"ranked_top20": ranked[:20], **met}
        reason_example = {"query_id": q.query_id, "query": q.query, "top_results": [r.__dict__ for r in ranked_results[:5]]}
        if len(reason_examples) < 12:
            reason_examples.append(reason_example)
        q_record["elapsed_s"] = time.perf_counter() - q_start
        per_query.append(q_record)
        write_json(progress, {"rows": query_rows, "per_query": q_record, "reason_example": reason_example})
        processed_new += 1

    systems = ["keyword", "bm25", "neural_embedding", "single_llm", "scholarloop_a"]
    aggregates = [aggregate(rows, s) for s in systems]
    by_system = {r["system"]: r for r in aggregates}
    a_f1 = [r["F1"] for r in rows if r["system"] == "scholarloop_a"]
    bm25_f1 = [r["F1"] for r in rows if r["system"] == "bm25"]
    sig = paired_bootstrap(a_f1, bm25_f1, n=bootstrap_n)
    other_mean = statistics.mean([by_system[s]["F1"] for s in ["keyword", "bm25", "neural_embedding", "single_llm"]])
    complete = len(per_query) == len(queries) and all(by_system[s]["queries"] == len(queries) for s in systems)
    wall_pass = bool(complete and sig["passed"] and by_system["scholarloop_a"]["F1"] >= other_mean and by_system["scholarloop_a"]["hallucinated_or_out_of_pool"] == 0)
    latencies = [r["elapsed_s"] for r in per_query]
    result = {
        "status": "PASS" if wall_pass else "BLOCKED" if complete else "INCOMPLETE",
        "query_count": len(queries),
        "completed_query_count": len(per_query),
        "processed_new_queries": processed_new,
        "protocol": {"top_k": top_k, "single_llm_prompt_k": pipe.prompt_k, "shared_candidate_pool": "keyword/BM25/neural top-k union; all systems scored or constrained on same pool", "neural_model": pipe.dense.model_name, "neural_model_version": pipe.dense.model_version, "neural_is_lsa": False, "temperature": 0, "seed": 42},
        "precheck": precheck,
        "aggregate": aggregates,
        "per_query": per_query,
        "hallucinated_or_out_of_pool": int(sum(r.get("hallucinated_or_out_of_pool", 0) for r in rows)),
        "efficiency": {"total_wall_s": time.perf_counter()-start_total, "total_query_elapsed_s": float(sum(latencies)), "p50_query_s": percentile(latencies, 50), "p95_query_s": percentile(latencies, 95), "total_tokens": int(sum(r.get("total_tokens", 0) for r in rows)), "avg_tokens_per_query": float(sum(r.get("total_tokens", 0) for r in rows) / max(1, len(per_query))), "api_calls_per_query": 2.0},
        "reason_examples": reason_examples,
    }
    result_name = "results.json" if complete else "partial_results.json"
    csv_name = "results.csv" if complete else "partial_results.csv"
    sig_name = "significance.json" if complete else "partial_significance.json"
    report_name = "A-main-evaluation-report.md" if complete else "A-main-evaluation-report.partial.md"
    write_json(report_dir / result_name, result)
    write_csv(report_dir / csv_name, rows)
    sig_out = {"scholarloop_a_vs_bm25_f1": sig, "scholarloop_a_f1": by_system["scholarloop_a"]["F1"], "other_baseline_mean_f1": float(other_mean), "passed": wall_pass}
    write_json(report_dir / sig_name, sig_out)
    write_report(report_dir / report_name, result, sig_out)
    if complete and not wall_pass:
        write_stop(report_dir / "010-stop-significance.md", result, sig_out)
    return {"status": result["status"], "query_count": len(queries), "completed_query_count": len(per_query), "processed_new_queries": processed_new, "report_dir": str(report_dir), "significance_passed": wall_pass}


def write_report(path: Path, result: dict[str, Any], sig: dict[str, Any]) -> None:
    lines = ["# M010 A-main evaluation report", "", f"- Status: **{result['status']}**", f"- Query count: {result['query_count']}", f"- Neural model: `{result['protocol']['neural_model']}`", "", "## Aggregate metrics", "| system | P@10 | R@20 | F1 | hallucinated | tokens | latency_s |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in result["aggregate"]:
        lines.append(f"| {r['system']} | {r['P@10']:.4f} | {r['R@20']:.4f} | {r['F1']:.4f} | {r['hallucinated_or_out_of_pool']} | {r['total_tokens']} | {r['total_latency_s']:.2f} |")
    boot = sig["scholarloop_a_vs_bm25_f1"]
    eff = result["efficiency"]
    proto = result["protocol"]
    lines += [
        "",
        "## Protocol",
        f"- Shared candidate pool: {proto['shared_candidate_pool']}",
        f"- Candidate top_k per local retriever: `{proto['top_k']}`",
        f"- Single-LLM prompt candidate cap: `{proto['single_llm_prompt_k']}`",
        f"- Neural is LSA: `{proto['neural_is_lsa']}`",
        f"- Temperature / seed: `{proto['temperature']}` / `{proto['seed']}`",
        "",
        "## Efficiency",
        f"- Total wall seconds: `{eff['total_wall_s']:.2f}`",
        f"- Sum of per-query elapsed seconds: `{eff['total_query_elapsed_s']:.2f}`",
        f"- P50 / P95 query seconds: `{eff['p50_query_s']:.2f}` / `{eff['p95_query_s']:.2f}`",
        f"- Total tokens: `{eff['total_tokens']}`",
        f"- API calls per query: `{eff['api_calls_per_query']}`",
        "",
        "## Significance",
        f"- Mean delta F1(A - BM25): `{boot['mean_delta']:.6f}`",
        f"- Bootstrap 95% CI: `[{boot['ci95'][0]:.6f}, {boot['ci95'][1]:.6f}]`",
        f"- Passed: `{sig['passed']}`",
        "",
        "## Explainability samples",
    ]
    for ex in result["reason_examples"][:5]:
        lines.append(f"### {ex['query_id']}")
        for r in ex["top_results"][:3]:
            lines.append(f"- `{r['corpusid']}` score={r['score']:.4f}; reason: {r['reason']}")
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")


def write_stop(path: Path, result: dict[str, Any], sig: dict[str, Any]) -> None:
    boot = sig["scholarloop_a_vs_bm25_f1"]
    text = f"""# M010 stop report - significance gate not passed\n\n- Status: BLOCKED\n- Reason: ScholarLoop-A did not pass the approved S1 wall against BM25.\n- Mean delta F1(A-BM25): {boot['mean_delta']:.6f}\n- Bootstrap 95% CI: [{boot['ci95'][0]:.6f}, {boot['ci95'][1]:.6f}]\n- Query count: {result['query_count']}\n\nPer plan Section 11, this is a mandatory stop condition. No acceptance criteria were changed.\n"""
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--report-dir", default="reports/m010")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--max-new", type=int, default=None, help="Process at most this many uncached queries, then write partial artifacts.")
    args = parser.parse_args(argv)
    out = evaluate(args.limit, args.bootstrap, Path(args.report_dir), args.top_k, args.max_new)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out["status"] == "PASS":
        return 0
    if out["status"] == "INCOMPLETE":
        return 4
    return 5


if __name__ == "__main__":
    raise SystemExit(main())

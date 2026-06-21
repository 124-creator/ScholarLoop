from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import scholarloop.config as config  # noqa: F401 - loads approved local env when present.
from scholarloop.gaps.detect import GapDetector, GapRunConfig, citation_signal_status
from scholarloop.gaps.narrate import NarrationResult, narrate_candidates
from scholarloop.utils import write_json


def _rows_for_display(candidates: list[dict[str, Any]], narrations: list[NarrationResult], limit: int = 50) -> dict[str, Any]:
    narration_by_idx = {n.candidate_index: n for n in narrations}
    rows = []
    concepts: dict[str, int] = {}
    for idx, candidate in enumerate(candidates[:limit]):
        concepts.setdefault(candidate["concept_a"], len(concepts))
        concepts.setdefault(candidate["concept_b"], len(concepts))
        narration = narration_by_idx.get(idx)
        counts = candidate["evidence"]["counts"]
        rows.append(
            {
                "id": f"gap_{idx:04d}",
                "concept_a": candidate["concept_a"],
                "concept_b": candidate["concept_b"],
                "score": candidate["score"],
                "evidence_status": candidate["evidence_status"],
                "counts": counts,
                "historical_evidence_ids": candidate["evidence"]["historical_evidence_ids"],
                "future_fill_example_ids": candidate["evidence"]["future_fill_example_ids"],
                "narration": narration.text if narration else None,
            }
        )
    matrix_edges = [
        {
            "source": row["concept_a"],
            "target": row["concept_b"],
            "past_cooccur_count": row["counts"]["past_cooccur_count"],
            "future_fill_count": row["counts"]["future_fill_count"],
            "evidence_status": row["evidence_status"],
        }
        for row in rows
    ]
    return {
        "format": "list_plus_relation_matrix",
        "s5_status_values": ["已有证据支持", "证据不足", "存在争议"],
        "items": rows,
        "concept_nodes": [{"id": idx, "label": label} for label, idx in sorted(concepts.items(), key=lambda kv: kv[1])],
        "matrix_edges": matrix_edges,
    }


def _write_report(report_dir: Path, result: dict[str, Any]) -> None:
    metrics = result["prediction"]["metrics"]
    lines = [
        "# M070 research-gap prediction report",
        "",
        f"Status: `{result['status']}`",
        f"Wall passed: `{result['wall_passed']}`",
        "",
        "## Operational definition",
        result["prediction"]["operational_definition"],
        "",
        "## Prediction wall",
        f"- Candidate fill rate: `{metrics['candidate_fill_rate']:.6f}` ({metrics['candidate_filled']}/{result['prediction']['candidate_count']})",
        f"- Random-pair baseline fill rate: `{metrics['baseline_fill_rate']:.6f}` ({metrics['baseline_filled']}/{result['prediction']['baseline_count']})",
        f"- Paired delta: `{metrics['paired_delta']:.6f}`",
        f"- Bootstrap CI95: `{metrics['bootstrap']['ci95']}`, passed=`{metrics['bootstrap']['passed']}`",
        f"- Permutation p(one-sided): `{metrics['permutation']['p_one_sided']:.6g}`, passed=`{metrics['permutation']['passed']}`",
        "",
        "## H5 narration",
        f"- Narration out of evidence ids: `{result['narration_out_of_evidence']}`",
        f"- Narrated candidates: `{result['narration_summary']['narrated']}`",
        "",
        "## Signals",
        f"- Primary: `{result['prediction']['signal']}`",
        f"- Citation signal status: `{result['citation_signal_status']['available']}` (adopted for primary wall: `{result['citation_signal_status']['adopted_for_primary_wall']}`)",
        "",
        "## Artifacts",
        "- `reports/m070/results.json`",
        "- `reports/m070/significance.json`",
        "- `reports/m070/gaps_display.json`",
        "- `reports/m070/spike/gap_schema_spike.json`",
    ]
    (report_dir / "评测报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _stop(report_dir: Path, status: str, reasons: list[str], payload: dict[str, Any]) -> int:
    result = {"status": status, "wall_passed": False, "stop_reasons": reasons, **payload}
    write_json(report_dir / "results.json", result)
    (report_dir / "STOP_REPORT.md").write_text(
        "# M070 stop report\n\n"
        + f"Status: `{status}`\n\n"
        + "## Reasons\n"
        + "\n".join(f"- {r}" for r in reasons)
        + "\n\nNo主体 was built beyond the allowed gate artifacts when the gate failed.\n",
        encoding="utf-8",
    )
    return 2


def run(args: argparse.Namespace) -> int:
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "spike").mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    base_cfg = GapRunConfig(
        corpus_path=args.corpus_path,
        cutoff_yyyymm=args.cutoff_yyyymm,
        recent_start_yyyymm=args.recent_start_yyyymm,
        future_end_yyyymm=args.future_end_yyyymm,
        top_n_concepts=args.top_n_concepts,
        candidate_k=args.candidate_k,
        bootstrap_n=args.bootstrap_n,
    )
    spike_cfg = base_cfg.spike()
    spike_result = GapDetector(spike_cfg).run()
    spike_result["gate"] = {
        "make_or_break": True,
        "passed": bool(spike_result["metrics"]["passed"]),
        "stop_if_failed": "Do not build M070主体 if schema spike does not significantly beat the random concept-pair baseline.",
    }
    write_json(report_dir / "spike" / "gap_schema_spike.json", spike_result)
    write_json(Path("spike/gaps/gap_schema_spike.json"), spike_result)
    if args.mode == "spike":
        write_json(report_dir / "final_summary.json", {"status": "spike_passed" if spike_result["metrics"]["passed"] else "blocked_schema_spike", "spike_passed": spike_result["metrics"]["passed"]})
        return 0 if spike_result["metrics"]["passed"] else 2
    if not spike_result["metrics"]["passed"]:
        return _stop(report_dir, "blocked_schema_spike_not_predictive", ["schema spike prediction was not significantly above random baseline"], {"spike": spike_result})

    full_result = GapDetector(base_cfg).run()
    if not full_result["metrics"]["passed"]:
        return _stop(report_dir, "blocked_full_prediction_not_significant", ["full prediction wall was not significantly above random baseline"], {"spike": spike_result, "prediction": full_result})

    narrations, narration_summary = narrate_candidates(full_result["candidates"], report_dir / "raw" / "llm", limit=args.narrate_top, use_llm=not args.no_llm)
    narration_rows = [asdict(n) for n in narrations]
    out_of_evidence = sum(len(n.out_of_evidence_ids) for n in narrations)
    citation_status = citation_signal_status()
    display = _rows_for_display(full_result["candidates"], narrations, limit=args.display_top)
    write_json(report_dir / "gaps_display.json", display)
    sig = {"gap_prediction_vs_random": full_result["metrics"]}
    write_json(report_dir / "significance.json", sig)
    result = {
        "status": "implemented_pending_review",
        "wall_passed": True,
        "stop_reasons": [],
        "x1_operational_definition": full_result["operational_definition"],
        "h5": {"narration_out_of_evidence": out_of_evidence, "llm_adds_papers_or_facts": False},
        "narration_out_of_evidence": out_of_evidence,
        "narration_summary": narration_summary,
        "narrations": narration_rows,
        "spike": {
            "path": "reports/m070/spike/gap_schema_spike.json",
            "status": spike_result["status"],
            "metrics": spike_result["metrics"],
            "config": spike_result["config"],
        },
        "prediction": full_result,
        "significance": sig,
        "citation_signal_status": citation_status,
        "protocol": {
            "temperature": 0,
            "seed": 42,
            "bootstrap_n": args.bootstrap_n,
            "self_labeling": False,
            "selection_uses_future": False,
            "future_used_only_for_evaluation": True,
            "primary_signal": "combination gap + time-sliced predictive validation",
            "random_baseline": "deterministic random concept pairs from the same eligible concept pool; no future-based selection",
            "allowed_writes": ["src/scholarloop/gaps/**", "src/scholarloop/eval/run_gaps.py", "spike/gaps/**", "tests/test_m070_*.py", "reports/m070/**"],
        },
        "elapsed_s": time.perf_counter() - started,
    }
    write_json(report_dir / "results.json", result)
    _write_report(report_dir, result)
    write_json(report_dir / "final_summary.json", {"status": result["status"], "wall_passed": True, "candidate_fill_rate": full_result["metrics"]["candidate_fill_rate"], "baseline_fill_rate": full_result["metrics"]["baseline_fill_rate"], "paired_delta": full_result["metrics"]["paired_delta"], "narration_out_of_evidence": out_of_evidence})
    stop_path = report_dir / "STOP_REPORT.md"
    if stop_path.exists():
        stop_path.unlink()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M070 research-gap discovery gate and prediction evaluation")
    parser.add_argument("--mode", choices=["spike", "full"], default="full")
    parser.add_argument("--report-dir", default="reports/m070")
    parser.add_argument("--corpus-path", default="reports/m060/cache/realscholarquery/corpus.jsonl")
    parser.add_argument("--cutoff-yyyymm", type=int, default=202401)
    parser.add_argument("--recent-start-yyyymm", type=int, default=202201)
    parser.add_argument("--future-end-yyyymm", type=int, default=202410)
    parser.add_argument("--top-n-concepts", type=int, default=1600)
    parser.add_argument("--candidate-k", type=int, default=500)
    parser.add_argument("--bootstrap-n", type=int, default=10000)
    parser.add_argument("--narrate-top", type=int, default=5)
    parser.add_argument("--display-top", type=int, default=50)
    parser.add_argument("--no-llm", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))

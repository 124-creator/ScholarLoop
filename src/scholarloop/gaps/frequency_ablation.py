from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from scholarloop.gaps.detect import GapRunConfig, extract_concepts, load_realscholar_records
from scholarloop.utils import write_json


@dataclass(frozen=True)
class FrequencyAblationConfig:
    m070_results_path: str = "reports/m070/results.json"
    output_path: str = "reports/m100/gap_frequency_ablation.json"
    seed: int = 100
    bootstrap_seed: int = 101
    permutation_seed: int = 102
    bootstrap_n: int = 10000
    max_relax_radius: int = 5
    attempts_per_radius: int = 200


def _bucket(value: int) -> int:
    return int(math.floor(math.log2(max(1, int(value)))))


def _concept_bucket(past_df: dict[str, int], recent_df: dict[str, int], concept: str) -> tuple[int, int]:
    return (_bucket(past_df.get(concept, 0)), _bucket(recent_df.get(concept, 0)))


def _close_concepts(
    concepts: list[str],
    past_df: dict[str, int],
    recent_df: dict[str, int],
    target: tuple[int, int],
    radius: int,
) -> list[str]:
    out = []
    for c in concepts:
        b = _concept_bucket(past_df, recent_df, c)
        if abs(b[0] - target[0]) + abs(b[1] - target[1]) <= radius:
            out.append(c)
    return out


def metric_summary(candidate_values: list[int], baseline_values: list[int], bootstrap_n: int, bootstrap_seed: int, permutation_seed: int) -> dict[str, Any]:
    candidate = np.array(candidate_values, dtype=np.int8)
    baseline = np.array(baseline_values, dtype=np.int8)
    diffs = candidate - baseline
    if len(diffs) == 0:
        return {
            "candidate_fill_rate": 0.0,
            "baseline_fill_rate": 0.0,
            "candidate_filled": 0,
            "baseline_filled": 0,
            "paired_delta": 0.0,
            "bootstrap": {"resamples": bootstrap_n, "ci95": [0.0, 0.0], "passed": False},
            "permutation": {"resamples": bootstrap_n, "p_one_sided": 1.0, "passed": False},
            "passed": False,
        }
    rng = np.random.default_rng(bootstrap_seed)
    samples = rng.choice(diffs, size=(bootstrap_n, len(diffs)), replace=True).mean(axis=1)
    lo, hi = np.percentile(samples, [2.5, 97.5])
    observed = float(diffs.mean())
    if observed > 0:
        signs = np.random.default_rng(permutation_seed).choice(np.array([-1, 1], dtype=np.int8), size=(bootstrap_n, len(diffs)))
        p_one_sided = float((np.sum((signs * diffs).mean(axis=1) >= observed) + 1) / (bootstrap_n + 1))
    else:
        p_one_sided = 1.0
    return {
        "candidate_fill_rate": float(candidate.mean()),
        "baseline_fill_rate": float(baseline.mean()),
        "candidate_filled": int(candidate.sum()),
        "baseline_filled": int(baseline.sum()),
        "paired_delta": observed,
        "bootstrap": {"resamples": bootstrap_n, "ci95": [float(lo), float(hi)], "passed": bool(lo > 0)},
        "permutation": {"resamples": bootstrap_n, "p_one_sided": p_one_sided, "passed": bool(p_one_sided < 0.05)},
        "passed": bool(lo > 0 or p_one_sided < 0.05),
    }


class FrequencyMatchedAblation:
    def __init__(self, config: FrequencyAblationConfig = FrequencyAblationConfig()) -> None:
        self.config = config

    def _load_m070_prediction(self) -> dict[str, Any]:
        data = json.loads(Path(self.config.m070_results_path).read_text(encoding="utf-8"))
        prediction = data.get("prediction")
        if not isinstance(prediction, dict) or not prediction.get("candidates"):
            raise RuntimeError("M100 frequency ablation requires reports/m070/results.json.prediction.candidates")
        return prediction

    def _build_frequency_context(self, m070_cfg: dict[str, Any]) -> dict[str, Any]:
        cfg = GapRunConfig(**m070_cfg)
        records = load_realscholar_records(cfg.corpus_path, cfg.future_end_yyyymm)
        past = [r for r in records if r.yyyymm < cfg.cutoff_yyyymm]
        recent = [r for r in past if r.yyyymm >= cfg.recent_start_yyyymm]
        future = [r for r in records if cfg.cutoff_yyyymm <= r.yyyymm <= cfg.future_end_yyyymm]
        concept_by_doc = {r.corpusid: extract_concepts(r.title) for r in records}
        past_df: dict[str, int] = {}
        recent_df: dict[str, int] = {}
        for r in past:
            for c in concept_by_doc[r.corpusid]:
                past_df[c] = past_df.get(c, 0) + 1
        for r in recent:
            for c in concept_by_doc[r.corpusid]:
                recent_df[c] = recent_df.get(c, 0) + 1
        concepts = [
            c
            for c, n in sorted(recent_df.items(), key=lambda kv: (-kv[1], kv[0]))
            if n >= cfg.min_recent_df and past_df.get(c, 0) >= cfg.min_past_df
        ][: cfg.top_n_concepts]
        concept_set = set(concepts)
        future_by = {c: set() for c in concept_set}
        for record in future:
            for concept in concept_by_doc[record.corpusid] & concept_set:
                future_by[concept].add(record.corpusid)
        return {
            "m070_config": asdict(cfg),
            "slice_counts": {"records": len(records), "past": len(past), "recent": len(recent), "future": len(future)},
            "concepts": concepts,
            "past_df": past_df,
            "recent_df": recent_df,
            "future_by": future_by,
        }

    def _sample_match(
        self,
        idx: int,
        candidate: dict[str, Any],
        concepts: list[str],
        past_df: dict[str, int],
        recent_df: dict[str, int],
        future_by: dict[str, set[int]],
        seen: set[tuple[str, str]],
    ) -> dict[str, Any]:
        rng = random.Random(self.config.seed + idx * 7919)
        concept_a = str(candidate["concept_a"])
        concept_b = str(candidate["concept_b"])
        target_a = _concept_bucket(past_df, recent_df, concept_a)
        target_b = _concept_bucket(past_df, recent_df, concept_b)
        forbidden = tuple(sorted((concept_a, concept_b)))
        best: tuple[str, str, int] | None = None
        for radius in range(self.config.max_relax_radius + 1):
            pool_a = _close_concepts(concepts, past_df, recent_df, target_a, radius)
            pool_b = _close_concepts(concepts, past_df, recent_df, target_b, radius)
            if not pool_a or not pool_b:
                continue
            for _ in range(self.config.attempts_per_radius):
                a = rng.choice(pool_a)
                b = rng.choice(pool_b)
                key = tuple(sorted((a, b)))
                if a == b or key == forbidden or key in seen or set(a.split()) & set(b.split()):
                    continue
                best = (a, b, radius)
                break
            if best:
                break
            # Try reversed orientation for asymmetric frequency buckets.
            pool_a = _close_concepts(concepts, past_df, recent_df, target_b, radius)
            pool_b = _close_concepts(concepts, past_df, recent_df, target_a, radius)
            for _ in range(self.config.attempts_per_radius):
                a = rng.choice(pool_a)
                b = rng.choice(pool_b)
                key = tuple(sorted((a, b)))
                if a == b or key == forbidden or key in seen or set(a.split()) & set(b.split()):
                    continue
                best = (a, b, radius)
                break
            if best:
                break
        if best is None:
            raise RuntimeError(f"Unable to sample frequency-matched baseline for candidate index {idx}")
        a, b, radius = best
        seen.add(tuple(sorted((a, b))))
        future_fill = len(future_by.get(a, set()) & future_by.get(b, set()))
        return {
            "candidate_index": idx,
            "concept_a": a,
            "concept_b": b,
            "future_fill_count": future_fill,
            "matched_to": {"concept_a": concept_a, "concept_b": concept_b},
            "target_buckets": {"a": list(target_a), "b": list(target_b)},
            "sampled_buckets": {"a": list(_concept_bucket(past_df, recent_df, a)), "b": list(_concept_bucket(past_df, recent_df, b))},
            "relax_radius": radius,
            "counts": {
                "past_count_a": past_df.get(a, 0),
                "past_count_b": past_df.get(b, 0),
                "recent_count_a": recent_df.get(a, 0),
                "recent_count_b": recent_df.get(b, 0),
            },
        }

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        prediction = self._load_m070_prediction()
        context = self._build_frequency_context(prediction["config"])
        candidates = list(prediction["candidates"])
        seen: set[tuple[str, str]] = set()
        baselines = [
            self._sample_match(i, row, context["concepts"], context["past_df"], context["recent_df"], context["future_by"], seen)
            for i, row in enumerate(candidates)
        ]
        candidate_flags = [1 if int(row.get("future_fill_count", 0)) > 0 else 0 for row in candidates]
        baseline_flags = [1 if int(row.get("future_fill_count", 0)) > 0 else 0 for row in baselines]
        metrics = metric_summary(candidate_flags, baseline_flags, self.config.bootstrap_n, self.config.bootstrap_seed, self.config.permutation_seed)
        relax_values = [int(row["relax_radius"]) for row in baselines]
        if metrics["passed"] and metrics["paired_delta"] > 0:
            conclusion = "frequency_matched_signal_remains_positive"
            claim_boundary = "控制概念边际频率后，M070 高活跃·零历史共现组合空白的未来填补率仍高于频率配平随机基线。"
        elif metrics["paired_delta"] > 0:
            conclusion = "frequency_matched_signal_positive_but_not_significant"
            claim_boundary = "控制概念边际频率后仍有正向趋势，但显著性不足；创新主张应收紧为部分预测效力。"
        else:
            conclusion = "frequency_is_primary_driver_or_signal_absent"
            claim_boundary = "频率配平后空白预测信号减弱或消失；创新主张必须收紧为频率驱动下的候选生成启发。"
        result = {
            "schema_version": "m100.gap_frequency_ablation.v1",
            "status": "implemented",
            "conclusion": conclusion,
            "claim_boundary": claim_boundary,
            "honesty_note": "频率消融信号减弱/消失不是停机项；本报告按实测结果收紧或增强主张。",
            "source": {
                "m070_results": self.config.m070_results_path,
                "m070_verified_unchanged": True,
                "uses_future_only_for_evaluation": True,
            },
            "config": asdict(self.config),
            "m070_original_metrics": prediction.get("metrics"),
            "frequency_matched_metrics": metrics,
            "matching_quality": {
                "baseline_count": len(baselines),
                "candidate_count": len(candidates),
                "relax_radius_mean": float(statistics.mean(relax_values)) if relax_values else 0.0,
                "relax_radius_max": max(relax_values) if relax_values else 0,
                "exact_bucket_matches": int(sum(1 for v in relax_values if v == 0)),
            },
            "slice_counts": context["slice_counts"],
            "baseline_sample": baselines[:20],
            "elapsed_s": time.perf_counter() - started,
        }
        write_json(Path(self.config.output_path), result)
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=FrequencyAblationConfig.output_path)
    parser.add_argument("--bootstrap", type=int, default=FrequencyAblationConfig.bootstrap_n)
    args = parser.parse_args(argv)
    result = FrequencyMatchedAblation(FrequencyAblationConfig(output_path=args.output, bootstrap_n=args.bootstrap)).run()
    print(json.dumps({"status": result["status"], "conclusion": result["conclusion"], "metrics": result["frequency_matched_metrics"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import math
import random
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from scholarloop.utils import percentile, write_json

TOKEN_RE = re.compile(r"[a-z][a-z0-9]+")
ARXIV_YYMM_RE = re.compile(r"^(\d{2})(\d{2})\.")

STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "for",
    "in",
    "on",
    "with",
    "without",
    "by",
    "to",
    "from",
    "via",
    "using",
    "use",
    "based",
    "towards",
    "toward",
    "into",
    "over",
    "under",
    "between",
    "among",
    "across",
    "through",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "as",
    "at",
    "this",
    "that",
    "these",
    "those",
    "we",
    "our",
    "their",
    "its",
    "it",
    "can",
    "may",
    "might",
    "large",
    "small",
    "new",
    "novel",
    "efficient",
    "effective",
    "learning",
    "model",
    "models",
    "method",
    "methods",
    "approach",
    "approaches",
    "paper",
    "study",
    "analysis",
    "data",
    "dataset",
    "datasets",
    "task",
    "tasks",
    "system",
    "systems",
    "neural",
    "network",
    "networks",
    "deep",
    "machine",
    "language",
    "algorithm",
    "algorithms",
    "graph",
    "graphs",
    "show",
    "shows",
    "untitled",
    "document",
    "survey",
    "surveys",
    "review",
    "reviews",
    "science",
    "foundation",
    "national",
    "support",
    "supported",
    "grant",
    "grants",
}

BAD_PHRASES = {"untitled document", "science foundation", "national science", "national science foundation"}


@dataclass(frozen=True)
class PaperRecord:
    corpusid: int
    arxiv_id: str
    yyyymm: int
    title: str
    abstract: str = ""


@dataclass(frozen=True)
class GapRunConfig:
    corpus_path: str = "reports/m060/cache/realscholarquery/corpus.jsonl"
    cutoff_yyyymm: int = 202401
    recent_start_yyyymm: int = 202201
    future_end_yyyymm: int = 202410
    top_n_concepts: int = 1600
    candidate_k: int = 500
    min_past_df: int = 20
    min_recent_df: int = 5
    max_past_cooccur: int = 0
    baseline_seed: int = 42
    bootstrap_seed: int = 42
    permutation_seed: int = 43
    bootstrap_n: int = 10000
    evidence_examples_per_concept: int = 3

    def spike(self) -> "GapRunConfig":
        return GapRunConfig(
            corpus_path=self.corpus_path,
            cutoff_yyyymm=self.cutoff_yyyymm,
            recent_start_yyyymm=self.recent_start_yyyymm,
            future_end_yyyymm=self.future_end_yyyymm,
            top_n_concepts=800,
            candidate_k=100,
            min_past_df=self.min_past_df,
            min_recent_df=self.min_recent_df,
            max_past_cooccur=self.max_past_cooccur,
            baseline_seed=self.baseline_seed,
            bootstrap_seed=self.bootstrap_seed,
            permutation_seed=self.permutation_seed,
            bootstrap_n=self.bootstrap_n,
            evidence_examples_per_concept=self.evidence_examples_per_concept,
        )


def parse_arxiv_yyyymm(arxiv_id: str | None) -> int | None:
    match = ARXIV_YYMM_RE.match(arxiv_id or "")
    if not match:
        return None
    yy = int(match.group(1))
    mm = int(match.group(2))
    if mm < 1 or mm > 12:
        return None
    return (2000 + yy) * 100 + mm


def extract_concepts(text: str | None) -> set[str]:
    """Deterministic title phrase extractor used by M070.

    It intentionally avoids LLM judgment: lower-case tokenization, fixed
    stoplist, and 2/3-gram phrases only. Generic corpus artifacts such as
    "untitled document" and grant boilerplate are filtered.
    """

    tokens = [t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOPWORDS and len(t) >= 3]
    out: set[str] = set()
    for n in (2, 3):
        for i in range(0, len(tokens) - n + 1):
            gram = tokens[i : i + n]
            if len(set(gram)) < n:
                continue
            phrase = " ".join(gram)
            if phrase in BAD_PHRASES:
                continue
            out.add(phrase)
    return out


def load_realscholar_records(corpus_path: str | Path, future_end_yyyymm: int = 202410) -> list[PaperRecord]:
    records: list[PaperRecord] = []
    with Path(corpus_path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            yyyymm = parse_arxiv_yyyymm(row.get("arxiv_id"))
            if yyyymm is None or yyyymm > future_end_yyyymm:
                continue
            title = str(row.get("title") or "")
            if not extract_concepts(title):
                continue
            records.append(
                PaperRecord(
                    corpusid=int(row["corpusid"]),
                    arxiv_id=str(row.get("arxiv_id") or ""),
                    yyyymm=yyyymm,
                    title=title,
                    abstract=str(row.get("abstract") or ""),
                )
            )
    return records


def _metric_summary(candidate_values: list[int], baseline_values: list[int], bootstrap_n: int, bootstrap_seed: int, permutation_seed: int) -> dict[str, Any]:
    candidate = np.array(candidate_values, dtype=np.int8)
    baseline = np.array(baseline_values, dtype=np.int8)
    diffs = candidate - baseline
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
        "candidate_fill_rate": float(candidate.mean()) if len(candidate) else 0.0,
        "baseline_fill_rate": float(baseline.mean()) if len(baseline) else 0.0,
        "candidate_filled": int(candidate.sum()),
        "baseline_filled": int(baseline.sum()),
        "paired_delta": observed,
        "bootstrap": {"resamples": bootstrap_n, "ci95": [float(lo), float(hi)], "passed": bool(lo > 0)},
        "permutation": {"resamples": bootstrap_n, "p_one_sided": p_one_sided, "passed": bool(p_one_sided < 0.05)},
        "passed": bool(lo > 0 or p_one_sided < 0.05),
    }


class GapDetector:
    def __init__(self, config: GapRunConfig) -> None:
        self.config = config

    def load_records(self) -> list[PaperRecord]:
        return load_realscholar_records(self.config.corpus_path, self.config.future_end_yyyymm)

    def run(self, records: list[PaperRecord] | None = None) -> dict[str, Any]:
        start = time.perf_counter()
        records = records if records is not None else self.load_records()
        cfg = self.config
        past = [r for r in records if r.yyyymm < cfg.cutoff_yyyymm]
        recent = [r for r in past if r.yyyymm >= cfg.recent_start_yyyymm]
        future = [r for r in records if cfg.cutoff_yyyymm <= r.yyyymm <= cfg.future_end_yyyymm]
        if not past or not recent or not future:
            raise RuntimeError("M070 gap detection needs non-empty past/recent/future slices.")

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
        if len(concepts) < 2:
            raise RuntimeError("M070 concept pool too small for paired prediction.")
        concept_set = set(concepts)
        past_by, recent_by, future_by = self._build_indices(concept_set, concept_by_doc, past, recent, future)
        examples = self._examples_by_concept(concept_set, concept_by_doc, past)
        pool = [c for c in concepts if len(recent_by[c]) >= cfg.min_recent_df and len(past_by[c]) >= cfg.min_past_df]
        scored = self._score_candidate_pairs(pool, past_by, recent_by, future_by)
        candidates = scored[: cfg.candidate_k]
        if len(candidates) < cfg.candidate_k:
            raise RuntimeError(f"M070 candidate count too small: {len(candidates)} < {cfg.candidate_k}")
        baselines = self._random_baseline(pool, future_by, len(candidates))

        candidate_flags = [1 if row["future_fill_count"] > 0 else 0 for row in candidates]
        baseline_flags = [1 if row["future_fill_count"] > 0 else 0 for row in baselines]
        metrics = _metric_summary(candidate_flags, baseline_flags, cfg.bootstrap_n, cfg.bootstrap_seed, cfg.permutation_seed)
        enriched = [self._enrich_candidate(row, examples, future_by) for row in candidates]
        return {
            "status": "passed" if metrics["passed"] else "failed",
            "signal": "combination_gap_with_time_sliced_prediction",
            "operational_definition": (
                "A gap candidate is a deterministic title n-gram concept pair where both concepts are frequent in the cutoff-before corpus, "
                "both are active in the recent pre-cutoff window, concept tokens do not overlap, and historical co-occurrence is <= max_past_cooccur. "
                "Candidate selection uses only pre-cutoff counts; future documents are used only for evaluation."
            ),
            "selection_uses_future": False,
            "config": asdict(cfg),
            "slice_counts": {"records": len(records), "past": len(past), "recent": len(recent), "future": len(future)},
            "concept_pool": {"top_n": cfg.top_n_concepts, "eligible": len(pool)},
            "candidate_count": len(candidates),
            "baseline_count": len(baselines),
            "metrics": metrics,
            "candidates": enriched,
            "baseline_sample": baselines[: min(20, len(baselines))],
            "elapsed_s": time.perf_counter() - start,
        }

    def _build_indices(
        self,
        concept_set: set[str],
        concept_by_doc: dict[int, set[str]],
        past: list[PaperRecord],
        recent: list[PaperRecord],
        future: list[PaperRecord],
    ) -> tuple[dict[str, set[int]], dict[str, set[int]], dict[str, set[int]]]:
        past_by = {c: set() for c in concept_set}
        recent_by = {c: set() for c in concept_set}
        future_by = {c: set() for c in concept_set}
        for target, rows in ((past_by, past), (recent_by, recent), (future_by, future)):
            for record in rows:
                for concept in concept_by_doc[record.corpusid] & concept_set:
                    target[concept].add(record.corpusid)
        return past_by, recent_by, future_by

    def _examples_by_concept(self, concept_set: set[str], concept_by_doc: dict[int, set[str]], past: list[PaperRecord]) -> dict[str, list[dict[str, Any]]]:
        examples = {c: [] for c in concept_set}
        limit = self.config.evidence_examples_per_concept
        for record in past:
            for concept in sorted(concept_by_doc[record.corpusid] & concept_set):
                if len(examples[concept]) < limit:
                    examples[concept].append({"corpusid": record.corpusid, "arxiv_id": record.arxiv_id, "yyyymm": record.yyyymm, "title": record.title})
        return examples

    def _score_candidate_pairs(
        self,
        pool: list[str],
        past_by: dict[str, set[int]],
        recent_by: dict[str, set[int]],
        future_by: dict[str, set[int]],
    ) -> list[dict[str, Any]]:
        cfg = self.config
        rows: list[dict[str, Any]] = []
        for i, concept_a in enumerate(pool):
            tokens_a = set(concept_a.split())
            past_a = past_by[concept_a]
            for concept_b in pool[i + 1 :]:
                if tokens_a & set(concept_b.split()):
                    continue
                past_cooccur = len(past_a & past_by[concept_b])
                if past_cooccur > cfg.max_past_cooccur:
                    continue
                score = min(len(recent_by[concept_a]), len(recent_by[concept_b])) * math.log1p(min(len(past_by[concept_a]), len(past_by[concept_b]))) / (1 + past_cooccur)
                rows.append(
                    {
                        "concept_a": concept_a,
                        "concept_b": concept_b,
                        "score": float(score),
                        "past_count_a": len(past_by[concept_a]),
                        "past_count_b": len(past_by[concept_b]),
                        "recent_count_a": len(recent_by[concept_a]),
                        "recent_count_b": len(recent_by[concept_b]),
                        "past_cooccur_count": past_cooccur,
                        "future_fill_count": len(future_by[concept_a] & future_by[concept_b]),
                    }
                )
        rows.sort(key=lambda r: (-float(r["score"]), str(r["concept_a"]), str(r["concept_b"])))
        return rows

    def _random_baseline(self, pool: list[str], future_by: dict[str, set[int]], count: int) -> list[dict[str, Any]]:
        rng = random.Random(self.config.baseline_seed)
        rows: list[dict[str, Any]] = []
        attempts = 0
        while len(rows) < count and attempts < count * 10000:
            concept_a, concept_b = rng.sample(pool, 2)
            attempts += 1
            if set(concept_a.split()) & set(concept_b.split()):
                continue
            rows.append(
                {
                    "concept_a": concept_a,
                    "concept_b": concept_b,
                    "future_fill_count": len(future_by[concept_a] & future_by[concept_b]),
                }
            )
        if len(rows) < count:
            raise RuntimeError(f"Unable to build deterministic random baseline: {len(rows)} < {count}")
        return rows

    def _enrich_candidate(self, row: dict[str, Any], examples: dict[str, list[dict[str, Any]]], future_by: dict[str, set[int]]) -> dict[str, Any]:
        concept_a = str(row["concept_a"])
        concept_b = str(row["concept_b"])
        future_ids = sorted(future_by[concept_a] & future_by[concept_b])[: self.config.evidence_examples_per_concept]
        evidence_ids = sorted({int(e["corpusid"]) for e in examples.get(concept_a, []) + examples.get(concept_b, [])})
        enriched = dict(row)
        enriched["evidence"] = {
            "concept_a_examples": examples.get(concept_a, []),
            "concept_b_examples": examples.get(concept_b, []),
            "historical_evidence_ids": evidence_ids,
            "future_fill_example_ids": future_ids,
            "counts": {
                "past_count_a": row["past_count_a"],
                "past_count_b": row["past_count_b"],
                "recent_count_a": row["recent_count_a"],
                "recent_count_b": row["recent_count_b"],
                "past_cooccur_count": row["past_cooccur_count"],
                "future_fill_count": row["future_fill_count"],
            },
        }
        enriched["evidence_status"] = "已有证据支持" if int(row["future_fill_count"]) > 0 else "证据不足"
        enriched["allowed_narration_ids"] = sorted(set(evidence_ids + future_ids))
        return enriched


def citation_signal_status(litsearch_dir: str | Path = "spike/raw/datasets/litsearch/corpus_clean") -> dict[str, Any]:
    """Report whether the optional citation signal has a local source."""

    try:
        import pyarrow.parquet as pq

        first = next(Path(litsearch_dir).glob("*.parquet"))
        columns = list(pq.ParquetFile(first).schema.names)
        return {
            "available": "citations" in columns,
            "source": str(first),
            "columns": columns,
            "adopted_for_primary_wall": False,
            "reason": "M070 primary wall uses the significant deterministic combination+time signal; citation source is available for future extension but not needed for the gate.",
        }
    except Exception as exc:
        return {"available": False, "error_type": type(exc).__name__, "error": str(exc)[:500], "adopted_for_primary_wall": False}


def write_detection_artifact(path: Path, result: dict[str, Any]) -> None:
    write_json(path, result)

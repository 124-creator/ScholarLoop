from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scholarloop.corpus.base import CorpusDocument, QueryRecord
from scholarloop.utils import write_json

TITLE_KEY_RE = re.compile(r"[^a-z0-9]+")
MODERN_ARXIV_RE = re.compile(r"^(\d{4})\.(\d{4,5})(?:v\d+)?$")


def normalize_title_key(title: str | None) -> str:
    """Return the PaSa/RealScholarQuery title key used inside cs_paper_2nd.zip."""
    return TITLE_KEY_RE.sub("", (title or "").lower())


def normalize_arxiv_id(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = text.removeprefix("arxiv:")
    text = re.sub(r"v\d+$", "", text)
    return text


def arxiv_id_to_corpusid(arxiv_id: str) -> int:
    """Stable numeric corpus id for official arXiv identifiers.

    Modern arXiv ids become their digit-only representation (2309.04564 ->
    230904564) so reports remain human-auditable. Legacy category ids are put
    in a high deterministic hash range to avoid collisions.
    """
    normalized = normalize_arxiv_id(arxiv_id)
    match = MODERN_ARXIV_RE.match(normalized)
    if match:
        return int(f"{match.group(1)}{match.group(2)}")
    return stable_synthetic_id("arxiv", normalized)


def stable_synthetic_id(namespace: str, value: str) -> int:
    digest = hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()
    return 900_000_000_000 + (int(digest[:14], 16) % 90_000_000_000)


@dataclass(frozen=True)
class GoldItem:
    query_id: str
    ordinal: int
    title: str
    arxiv_id: str
    title_key: str
    resolvable: bool
    corpusid: int | None
    method: str
    reason: str | None = None


class RealScholarQueryCorpus:
    """Local RealScholarQuery/PaSa adapter for M060.

    The adapter treats the official test.jsonl and paper_database as read-only.
    Gold reachability follows the human-approved dual criterion:
    arxiv_id in id2paper OR normalized answer title in cs_paper_2nd.zip.
    """

    def __init__(self, raw_root: Path | str = Path("reports/m060/raw/pasa-dataset"), cache_dir: Path | str = Path("reports/m060/cache/realscholarquery")) -> None:
        self.raw_root = Path(raw_root)
        self.cache_dir = Path(cache_dir)
        self.query_path = self.raw_root / "RealScholarQuery" / "test.jsonl"
        self.paper_dir = self.raw_root / "paper_database"
        self.id2paper_path = self.paper_dir / "id2paper.json"
        self.zip_path = self.paper_dir / "cs_paper_2nd.zip"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._id2paper: dict[str, str] | None = None
        self._zip_names: set[str] | None = None
        self._title_to_arxiv: dict[str, str] | None = None
        self._title_to_corpusid: dict[str, int] | None = None
        self._corpus: pd.DataFrame | None = None
        self.id_to_index: dict[int, int] = {}

    def validate_raw_files(self) -> dict[str, Any]:
        files = {
            "test_jsonl": self.query_path,
            "id2paper_json": self.id2paper_path,
            "cs_paper_zip": self.zip_path,
        }
        missing = [name for name, path in files.items() if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing RealScholarQuery/PaSa files: {missing}")
        return {name: {"path": str(path), "bytes": path.stat().st_size} for name, path in files.items()}

    def load_id2paper(self) -> dict[str, str]:
        if self._id2paper is None:
            with self.id2paper_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._id2paper = {normalize_arxiv_id(k): str(v) for k, v in data.items()}
        return self._id2paper

    def zip_names(self) -> set[str]:
        if self._zip_names is None:
            with zipfile.ZipFile(self.zip_path) as zf:
                self._zip_names = {name for name in zf.namelist() if name and not name.endswith("/")}
        return self._zip_names

    def title_to_arxiv(self) -> dict[str, str]:
        if self._title_to_arxiv is None:
            out: dict[str, str] = {}
            for arxiv_id, title in self.load_id2paper().items():
                key = normalize_title_key(title)
                if key and key not in out:
                    out[key] = arxiv_id
            self._title_to_arxiv = out
        return self._title_to_arxiv

    def title_to_corpusid(self) -> dict[str, int]:
        if self._title_to_corpusid is None:
            out: dict[str, int] = {}
            for key, arxiv_id in self.title_to_arxiv().items():
                out[key] = arxiv_id_to_corpusid(arxiv_id)
            for key in self.zip_names():
                out.setdefault(key, stable_synthetic_id("title", key))
            self._title_to_corpusid = out
        return self._title_to_corpusid

    def load_raw_queries(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.query_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def audit_gold(self) -> dict[str, Any]:
        id2paper = self.load_id2paper()
        zip_names = self.zip_names()
        title_to_corpusid = self.title_to_corpusid()
        raw_queries = self.load_raw_queries()
        gold_items: list[GoldItem] = []
        per_query_missing: list[dict[str, Any]] = []
        unexpected_causes: set[str] = set()

        for row in raw_queries:
            qid = str(row.get("qid") or row.get("id") or f"q{len(per_query_missing)}")
            titles = list(row.get("answer") or [])
            arxiv_ids = list(row.get("answer_arxiv_id") or [])
            max_len = max(len(titles), len(arxiv_ids))
            missing_count = 0
            for i in range(max_len):
                title = str(titles[i]) if i < len(titles) else ""
                arxiv_id = normalize_arxiv_id(str(arxiv_ids[i]) if i < len(arxiv_ids) else "")
                key = normalize_title_key(title)
                corpusid: int | None = None
                method = "unresolved"
                reason: str | None = None
                if arxiv_id and arxiv_id in id2paper:
                    corpusid = arxiv_id_to_corpusid(arxiv_id)
                    method = "arxiv_id_in_id2paper"
                elif key and key in zip_names:
                    corpusid = title_to_corpusid[key]
                    method = "normalized_title_in_cs_paper_zip"
                else:
                    missing_count += 1
                    if not arxiv_id and not key:
                        reason = "missing_arxiv_id_and_title"
                        unexpected_causes.add(reason)
                    elif not arxiv_id:
                        reason = "missing_arxiv_id_and_title_not_in_zip"
                        unexpected_causes.add(reason)
                    elif not key:
                        reason = "title_normalizes_empty_and_arxiv_not_in_id2paper"
                        unexpected_causes.add(reason)
                    else:
                        reason = "not_in_id2paper_and_title_not_in_zip"
                gold_items.append(
                    GoldItem(
                        query_id=qid,
                        ordinal=i,
                        title=title,
                        arxiv_id=arxiv_id,
                        title_key=key,
                        resolvable=corpusid is not None,
                        corpusid=corpusid,
                        method=method,
                        reason=reason,
                    )
                )
            per_query_missing.append({"query_id": qid, "gold_count": max_len, "unresolvable_count": missing_count})

        total = len(gold_items)
        resolvable = [g for g in gold_items if g.resolvable]
        unresolvable = [g for g in gold_items if not g.resolvable]
        queries_with_missing = [row for row in per_query_missing if row["unresolvable_count"]]
        return {
            "benchmark": "RealScholarQuery/PaSa",
            "query_count": len(raw_queries),
            "official_gold_count": total,
            "resolvable_gold_count": len(resolvable),
            "unresolvable_gold_count": len(unresolvable),
            "resolvable_ratio": len(resolvable) / total if total else 0.0,
            "queries_with_unresolvable_gold_count": len(queries_with_missing),
            "per_query_unresolvable": queries_with_missing,
            "unresolvable_gold": [g.__dict__ for g in unresolvable],
            "dual_verification_method": {
                "arxiv_path": "normalize answer_arxiv_id; check membership in paper_database/id2paper.json keys",
                "title_path": "normalize answer title with [^a-z0-9]+ removal; check membership in cs_paper_2nd.zip namelist",
                "resolvable_if": "arxiv_path OR title_path",
                "full791_policy": "unresolvable official gold are represented by unreachable synthetic ids and count as misses for every system",
            },
            "unexpected_unparseable_causes": sorted(unexpected_causes),
            "raw_files": self.validate_raw_files(),
        }

    def load_queries(self) -> tuple[list[QueryRecord], dict[str, dict[str, Any]], dict[str, Any]]:
        audit = self.audit_gold()
        raw_queries = self.load_raw_queries()
        items_by_q: dict[str, list[dict[str, Any]]] = {}
        for item in audit["unresolvable_gold"]:
            items_by_q.setdefault(item["query_id"], []).append(item)

        id2paper = self.load_id2paper()
        zip_names = self.zip_names()
        title_to_corpusid = self.title_to_corpusid()
        query_records: list[QueryRecord] = []
        gold_meta: dict[str, dict[str, Any]] = {}
        for row in raw_queries:
            qid = str(row.get("qid") or row.get("id") or f"q{len(query_records)}")
            query = str(row.get("question") or row.get("query") or "")
            titles = list(row.get("answer") or [])
            arxiv_ids = list(row.get("answer_arxiv_id") or [])
            max_len = max(len(titles), len(arxiv_ids))
            resolvable_ids: list[int] = []
            full_ids: list[int] = []
            item_rows: list[dict[str, Any]] = []
            for i in range(max_len):
                title = str(titles[i]) if i < len(titles) else ""
                arxiv_id = normalize_arxiv_id(str(arxiv_ids[i]) if i < len(arxiv_ids) else "")
                key = normalize_title_key(title)
                corpusid: int | None = None
                method = "unresolved"
                reason = None
                if arxiv_id and arxiv_id in id2paper:
                    corpusid = arxiv_id_to_corpusid(arxiv_id)
                    method = "arxiv_id_in_id2paper"
                elif key and key in zip_names:
                    corpusid = title_to_corpusid[key]
                    method = "normalized_title_in_cs_paper_zip"
                else:
                    reason = "not_in_id2paper_and_title_not_in_zip" if arxiv_id and key else "missing_required_gold_fields"
                    corpusid = stable_synthetic_id("unresolvable-gold", f"{qid}:{i}:{arxiv_id}:{key}")
                if method != "unresolved":
                    resolvable_ids.append(int(corpusid))
                full_ids.append(int(corpusid))
                item_rows.append(
                    {
                        "ordinal": i,
                        "title": title,
                        "arxiv_id": arxiv_id,
                        "title_key": key,
                        "corpusid": int(corpusid),
                        "resolvable": method != "unresolved",
                        "method": method,
                        "reason": reason,
                    }
                )
            query_records.append(QueryRecord(query_id=qid, query=query, gold=tuple(sorted(set(resolvable_ids)))))
            gold_meta[qid] = {
                "query_id": qid,
                "question": query,
                "resolvable_gold": sorted(set(resolvable_ids)),
                "full_gold": sorted(set(full_ids)),
                "official_gold_count": max_len,
                "unresolvable_count": max_len - len(set(resolvable_ids)),
                "gold_items": item_rows,
            }
        return query_records, gold_meta, audit

    def _read_zip_payload(self, zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
        try:
            payload = json.loads(zf.read(name).decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def build_corpus_cache(self, force: bool = False) -> dict[str, Any]:
        corpus_path = self.cache_dir / "corpus.jsonl"
        meta_path = self.cache_dir / "corpus_meta.json"
        if corpus_path.exists() and meta_path.exists() and not force:
            return json.loads(meta_path.read_text(encoding="utf-8"))

        start = time.perf_counter()
        id2paper = self.load_id2paper()
        zip_names = self.zip_names()
        title_to_arxiv = self.title_to_arxiv()
        seen_ids: set[int] = set()
        seen_zip_names: set[str] = set()
        rows_written = 0
        id2_with_zip = 0
        id2_without_zip = 0
        zip_only = 0

        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = corpus_path.with_suffix(".jsonl.tmp")
        with zipfile.ZipFile(self.zip_path) as zf, tmp_path.open("w", encoding="utf-8") as out:
            for arxiv_id, title in id2paper.items():
                key = normalize_title_key(title)
                corpusid = arxiv_id_to_corpusid(arxiv_id)
                payload: dict[str, Any] = {}
                if key in zip_names:
                    payload = self._read_zip_payload(zf, key)
                    seen_zip_names.add(key)
                    id2_with_zip += 1
                else:
                    id2_without_zip += 1
                final_title = str(payload.get("title") or title)
                abstract = str(payload.get("abstract") or "")
                row = {
                    "corpusid": corpusid,
                    "arxiv_id": arxiv_id,
                    "title": final_title,
                    "abstract": abstract,
                    "title_key": key,
                    "source": "id2paper+zip" if payload else "id2paper_only",
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                seen_ids.add(corpusid)
                rows_written += 1

            for key in sorted(zip_names - seen_zip_names):
                if key in title_to_arxiv:
                    continue
                payload = self._read_zip_payload(zf, key)
                if not payload:
                    continue
                corpusid = stable_synthetic_id("title", key)
                if corpusid in seen_ids:
                    continue
                row = {
                    "corpusid": corpusid,
                    "arxiv_id": "",
                    "title": str(payload.get("title") or key),
                    "abstract": str(payload.get("abstract") or ""),
                    "title_key": key,
                    "source": "zip_only",
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                seen_ids.add(corpusid)
                zip_only += 1
                rows_written += 1

        tmp_path.replace(corpus_path)
        meta = {
            "benchmark": "RealScholarQuery/PaSa paper_database",
            "corpus_jsonl": str(corpus_path),
            "rows": rows_written,
            "id2paper_records": len(id2paper),
            "zip_entries": len(zip_names),
            "id2paper_with_zip_payload": id2_with_zip,
            "id2paper_without_zip_payload": id2_without_zip,
            "zip_only_rows": zip_only,
            "elapsed_s": time.perf_counter() - start,
            "created_at_unix": time.time(),
        }
        write_json(meta_path, meta)
        return meta

    def load_corpus(self, force: bool = False) -> pd.DataFrame:
        if self._corpus is not None and not force:
            return self._corpus
        self.build_corpus_cache(force=force)
        corpus_path = self.cache_dir / "corpus.jsonl"
        rows: list[dict[str, Any]] = []
        with corpus_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        df = pd.DataFrame(rows)
        df["corpusid"] = df["corpusid"].astype("int64")
        df["title"] = df["title"].fillna("").astype(str)
        df["abstract"] = df["abstract"].fillna("").astype(str)
        df["text"] = (df["title"] + "\n" + df["abstract"]).astype(str)
        self._corpus = df
        self.id_to_index = {int(cid): i for i, cid in enumerate(df["corpusid"].tolist())}
        return df

    @property
    def corpus_ids(self):
        df = self.load_corpus()
        return df["corpusid"].to_numpy(dtype="int64")

    def iter_documents(self) -> Iterable[CorpusDocument]:
        df = self.load_corpus()
        for row in df.itertuples(index=False):
            yield CorpusDocument(corpusid=int(row.corpusid), title=str(row.title), abstract=str(row.abstract))
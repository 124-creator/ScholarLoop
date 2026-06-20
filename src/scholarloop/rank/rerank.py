from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sentence_transformers import CrossEncoder


DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _safe_query_id(query_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in query_id)


def _candidate_hash(candidate_ids: list[int], model_name: str) -> str:
    h = hashlib.sha256()
    h.update(model_name.encode("utf-8"))
    for cid in candidate_ids:
        h.update(str(int(cid)).encode("ascii"))
        h.update(b",")
    return h.hexdigest()[:16]


class CrossEncoderReranker:
    """Cached cross-encoder scorer for M040 A-v2 candidates."""

    def __init__(
        self,
        cache_dir: Path,
        model_name: str = DEFAULT_RERANK_MODEL,
        batch_size: int = 32,
        device: str = "cpu",
        local_files_only: bool = False,
    ) -> None:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self.local_files_only = local_files_only
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self.model_name, device=self.device, local_files_only=self.local_files_only)
        return self._model

    def cache_path(self, query_id: str, candidate_ids: list[int]) -> Path:
        stem = f"rerank_{_safe_query_id(query_id)}_{_candidate_hash(candidate_ids, self.model_name)}"
        return self.cache_dir / f"{stem}.json"

    def score(
        self,
        query_id: str,
        query: str,
        candidate_ids: list[int],
        corpus: pd.DataFrame,
        id_to_index: dict[int, int],
    ) -> dict[int, float]:
        path = self.cache_path(query_id, candidate_ids)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {int(cid): float(score) for cid, score in data["scores"].items()}
        pairs: list[tuple[str, str]] = []
        valid_ids: list[int] = []
        for cid in candidate_ids:
            idx = id_to_index.get(int(cid))
            if idx is None:
                continue
            row = corpus.iloc[idx]
            text = f"{row['title']}\n{row['abstract']}"
            pairs.append((query, " ".join(str(text).split())))
            valid_ids.append(int(cid))
        if not pairs:
            return {}
        values = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)
        arr = np.asarray(values, dtype=np.float32).reshape(-1)
        out = {cid: float(arr[i]) for i, cid in enumerate(valid_ids)}
        path.write_text(
            json.dumps(
                {
                    "query_id": query_id,
                    "model_name": self.model_name,
                    "device": self.device,
                    "candidate_count": len(valid_ids),
                    "scores": {str(k): v for k, v in out.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return out

    def metadata(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "cache_dir": str(self.cache_dir),
            "open_source": True,
            "offline_capable_after_cache": True,
            "estimated_download_under_2gb": True,
        }

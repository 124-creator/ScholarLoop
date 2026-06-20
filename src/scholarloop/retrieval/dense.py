from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


class DenseRetriever:
    def __init__(self, docs: list[str], cache_dir: Path, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", batch_size: int = 128) -> None:
        self.docs = docs
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name)
        self.model_version = self._model_version()
        self.embeddings = self._load_or_encode_docs()

    def _model_version(self) -> str:
        mods = getattr(self.model, "_modules", {})
        return f"{self.model_name}; dim={self.model.get_sentence_embedding_dimension()}; modules={list(mods.keys())}"

    def _fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(self.model_name.encode())
        h.update(str(len(self.docs)).encode())
        for text in self.docs[:10] + self.docs[-10:]:
            h.update(text[:256].encode(errors="ignore"))
        return h.hexdigest()[:16]

    def _paths(self) -> tuple[Path, Path]:
        fp = self._fingerprint()
        return self.cache_dir / f"dense_{fp}.npy", self.cache_dir / f"dense_{fp}.json"

    def _load_or_encode_docs(self) -> np.ndarray:
        npy, meta = self._paths()
        if npy.exists() and meta.exists():
            return np.load(npy).astype(np.float32)
        emb = self.model.encode(self.docs, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=True, convert_to_numpy=True).astype(np.float32)
        np.save(npy, emb)
        meta.write_text(json.dumps({"model_name": self.model_name, "model_version": self.model_version, "count": len(self.docs), "shape": list(emb.shape)}, indent=2), encoding="utf-8")
        return emb

    def scores(self, query: str) -> np.ndarray:
        q = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)[0]
        return (self.embeddings @ q).astype(np.float32)

    def batch_scores(self, queries: list[str]) -> np.ndarray:
        q = self.model.encode(queries, batch_size=min(self.batch_size, 64), normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
        return (q @ self.embeddings.T).astype(np.float32)

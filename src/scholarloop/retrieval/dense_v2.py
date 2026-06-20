from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

import numpy as np


DEFAULT_DENSE_V2_MODEL = "BAAI/bge-small-en-v1.5"


def _model_slug(model_name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in model_name)[:80]


def text_for_model(text: str, model_name: str, is_query: bool) -> str:
    """Apply retrieval-model conventions without changing the source text."""
    name = model_name.lower()
    stripped = " ".join((text or "").split())
    if "e5" in name:
        return ("query: " if is_query else "passage: ") + stripped
    if "bge" in name and is_query:
        return "Represent this sentence for searching relevant passages: " + stripped
    return stripped


class DenseV2Retriever:
    """Open-source dense retriever used only by M040 A-v2.

    The class intentionally does not modify or subclass the M010 DenseRetriever:
    A-v1 remains frozen and this path writes only to the caller-provided M040
    cache directory.
    """

    def __init__(
        self,
        docs: list[str],
        cache_dir: Path,
        model_name: str = DEFAULT_DENSE_V2_MODEL,
        batch_size: int = 64,
        device: str = "cpu",
        local_files_only: bool = False,
        encode_chunk_size: int = 4096,
    ) -> None:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        self.docs = docs
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self.local_files_only = local_files_only
        self.encode_chunk_size = encode_chunk_size
        from sentence_transformers import SentenceTransformer  # optional heavy dependency
        self.model = SentenceTransformer(model_name, device=device, local_files_only=local_files_only)
        self.model_version = self._model_version()
        self.embeddings = self._load_or_encode_docs()

    def _model_version(self) -> str:
        dim = getattr(self.model, "get_sentence_embedding_dimension", self.model.get_embedding_dimension)()
        mods = getattr(self.model, "_modules", {})
        return f"{self.model_name}; dim={dim}; modules={list(mods.keys())}; device={self.device}"

    def _fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(self.model_name.encode("utf-8"))
        h.update(self.device.encode("utf-8"))
        h.update(str(len(self.docs)).encode("utf-8"))
        for text in self.docs[:10] + self.docs[-10:]:
            h.update(text[:512].encode("utf-8", errors="ignore"))
        return h.hexdigest()[:16]

    def _paths(self) -> tuple[Path, Path]:
        stem = f"dense_v2_{_model_slug(self.model_name)}_{self._fingerprint()}"
        return self.cache_dir / f"{stem}.npy", self.cache_dir / f"{stem}.json"

    def _load_or_encode_docs(self) -> np.ndarray:
        npy, meta = self._paths()
        if npy.exists() and meta.exists():
            return np.load(npy).astype(np.float32)
        chunk_dir = self.cache_dir / f"{npy.stem}_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunks: list[np.ndarray] = []
        for start in range(0, len(self.docs), self.encode_chunk_size):
            end = min(len(self.docs), start + self.encode_chunk_size)
            chunk_path = chunk_dir / f"chunk_{start:06d}_{end:06d}.npy"
            if chunk_path.exists():
                chunks.append(np.load(chunk_path).astype(np.float32))
                continue
            encoded_docs = [text_for_model(text, self.model_name, is_query=False) for text in self.docs[start:end]]
            chunk = self.model.encode(
                encoded_docs,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=True,
                convert_to_numpy=True,
            ).astype(np.float32)
            np.save(chunk_path, chunk)
            progress = {
                "model_name": self.model_name,
                "encoded_until": end,
                "count": len(self.docs),
                "chunk_path": str(chunk_path),
                "batch_size": self.batch_size,
                "encode_chunk_size": self.encode_chunk_size,
                "device": self.device,
            }
            (chunk_dir / "progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
            chunks.append(chunk)
        emb = np.vstack(chunks).astype(np.float32)
        np.save(npy, emb)
        meta.write_text(
            json.dumps(
                {
                    "model_name": self.model_name,
                    "model_version": self.model_version,
                    "count": len(self.docs),
                    "shape": list(emb.shape),
                    "batch_size": self.batch_size,
                    "encode_chunk_size": self.encode_chunk_size,
                    "device": self.device,
                    "local_files_only": self.local_files_only,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return emb

    def encode_queries(self, queries: Iterable[str]) -> np.ndarray:
        prepared = [text_for_model(q, self.model_name, is_query=True) for q in queries]
        if not prepared:
            return np.zeros((0, self.embeddings.shape[1]), dtype=np.float32)
        return self.model.encode(
            prepared,
            batch_size=min(self.batch_size, 64),
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype(np.float32)

    def scores(self, query: str) -> np.ndarray:
        q = self.encode_queries([query])[0]
        return (self.embeddings @ q).astype(np.float32)

    def batch_scores(self, queries: list[str]) -> np.ndarray:
        q = self.encode_queries(queries)
        return (q @ self.embeddings.T).astype(np.float32)

    def metadata(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "device": self.device,
            "batch_size": self.batch_size,
            "encode_chunk_size": self.encode_chunk_size,
            "cache_dir": str(self.cache_dir),
            "open_source": True,
            "offline_capable_after_cache": True,
            "estimated_download_under_2gb": True,
        }


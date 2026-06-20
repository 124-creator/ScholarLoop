from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


REDACT_KEYS = {"api_key", "key", "token", "apikey"}


def stable_params(params: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in sorted((params or {}).items()):
        if value is None:
            continue
        if key.lower() in REDACT_KEYS:
            continue
        out[key] = str(value)
    return out


def redact_params(params: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in sorted((params or {}).items()):
        if value is None:
            continue
        out[key] = "<redacted>" if key.lower() in REDACT_KEYS else str(value)
    return out


def cache_digest(method: str, url: str, params: dict[str, Any] | None) -> str:
    h = hashlib.sha256()
    h.update(method.upper().encode("utf-8"))
    h.update(b"\n")
    h.update(url.encode("utf-8"))
    h.update(b"\n")
    h.update(urlencode(stable_params(params), doseq=True).encode("utf-8"))
    return h.hexdigest()[:24]


@dataclass(frozen=True)
class CacheEntry:
    path: Path
    source: str
    method: str
    url: str
    params: dict[str, str]
    fetched_at: str
    status_code: int
    headers: dict[str, str]
    body_json: Any


class ResponseCache:
    def __init__(self, root: Path = Path("reports/m050/cache")) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, source: str, method: str, url: str, params: dict[str, Any] | None = None) -> Path:
        safe_source = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in source)
        digest = cache_digest(method, url, params)
        return self.root / safe_source / f"{digest}.json"

    def exists(self, source: str, method: str, url: str, params: dict[str, Any] | None = None) -> bool:
        return self.path_for(source, method, url, params).exists()

    def read(self, source: str, method: str, url: str, params: dict[str, Any] | None = None) -> CacheEntry:
        return self.read_path(self.path_for(source, method, url, params))

    def read_path(self, path: Path | str) -> CacheEntry:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return CacheEntry(
            path=p,
            source=data["source"],
            method=data["method"],
            url=data["url"],
            params=dict(data.get("params") or {}),
            fetched_at=data["fetched_at"],
            status_code=int(data["status_code"]),
            headers=dict(data.get("headers") or {}),
            body_json=data.get("body_json"),
        )

    def write(
        self,
        path: Path,
        *,
        source: str,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        fetched_at: str,
        status_code: int,
        headers: dict[str, str],
        body_json: Any,
    ) -> CacheEntry:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": "m050.cache_entry.v1",
            "source": source,
            "method": method.upper(),
            "url": url,
            "params": redact_params(params),
            "fetched_at": fetched_at,
            "status_code": status_code,
            "headers": headers,
            "body_json": body_json,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.read_path(path)

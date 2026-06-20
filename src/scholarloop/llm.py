from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

import scholarloop.config as config
from scholarloop.utils import redact, write_json


def _json_from_content(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def _safe_dump(resp: Any, prompt_info: dict[str, Any], elapsed_s: float) -> dict[str, Any]:
    data = resp.model_dump() if hasattr(resp, "model_dump") else json.loads(resp.json())
    data["_m010_meta"] = {"prompt_info": prompt_info, "elapsed_s": elapsed_s}
    return data


def _content_from_dump(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content") or ""


def _backup_bad(raw_path: Path, reason: str) -> Path:
    backup = raw_path.with_name(f"{raw_path.name}.bad-{reason}-{int(time.time()*1000)}")
    raw_path.rename(backup)
    return backup


class LLMClient:
    def __init__(self, raw_dir: Path, max_tokens: int = 4096) -> None:
        config.require_llm_env()
        import os
        self.base_url = os.environ["LLM_BASE_URL"]
        self.model = os.environ["LLM_MODEL"]
        self.client = OpenAI(base_url=self.base_url, api_key=os.environ["LLM_API_KEY"])
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.max_tokens = max_tokens

    def precheck(self) -> dict[str, Any]:
        raw = self.raw_dir / "precheck.json"
        result = {"present": config.PRESENT, "valid": False, "model": self.model, "base_url_present": bool(self.base_url)}
        try:
            start = time.perf_counter()
            resp = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": "Return exactly OK."}], temperature=0, seed=42, max_tokens=512)
            result.update({"valid": True, "elapsed_s": time.perf_counter()-start, "usage": resp.usage.model_dump() if getattr(resp, "usage", None) else None, "content_preview": (resp.choices[0].message.content if resp.choices else "")[:20]})
        except Exception as exc:
            result.update({"valid": False, "exception_type": type(exc).__name__, "exception": redact(str(exc))[:1000]})
        write_json(raw, result)
        return result

    def chat_json(self, name: str, system: str, user: str, prompt_info: dict[str, Any], max_tokens: int | None = None) -> tuple[Any, dict[str, Any]]:
        raw_path = self.raw_dir / f"{name}.json"
        if raw_path.exists():
            data = json.loads(raw_path.read_text(encoding="utf-8"))
            try:
                parsed = _json_from_content(_content_from_dump(data))
                return parsed, {"cached": True, "raw_path": str(raw_path), "usage": data.get("usage") or {}, "elapsed_s": data.get("_m010_meta", {}).get("elapsed_s", 0.0), "model": data.get("model") or self.model}
            except Exception:
                _backup_bad(raw_path, "invalid_json_cache")
        errors: list[str] = []
        base_tokens = max_tokens or self.max_tokens
        for attempt in range(3):
            retry_suffix = "" if attempt == 0 else "\n\nYour previous response was invalid or empty. Return one valid JSON object only, with no markdown and no prose."
            attempt_info = dict(prompt_info)
            attempt_info["retry_attempt"] = attempt
            kwargs = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user + retry_suffix}],
                "temperature": 0,
                "seed": 42,
                "max_tokens": base_tokens if attempt == 0 else max(base_tokens, 2048),
                "response_format": {"type": "json_object"},
            }
            start = time.perf_counter()
            try:
                resp = self.client.chat.completions.create(**kwargs)
            except Exception as exc:
                if "json" not in str(exc).lower() and "response_format" not in str(exc).lower():
                    raise
                kwargs.pop("response_format", None)
                resp = self.client.chat.completions.create(**kwargs)
            elapsed = time.perf_counter() - start
            dump = _safe_dump(resp, attempt_info, elapsed)
            write_json(raw_path, dump)
            try:
                parsed = _json_from_content(resp.choices[0].message.content if resp.choices else "")
                return parsed, {"cached": False, "raw_path": str(raw_path), "usage": resp.usage.model_dump() if getattr(resp, "usage", None) else {}, "elapsed_s": elapsed, "model": getattr(resp, "model", self.model)}
            except Exception as exc:
                backup = _backup_bad(raw_path, f"invalid_json_fresh_attempt{attempt}")
                errors.append(f"attempt={attempt} backup={backup} error={type(exc).__name__}")
        raise RuntimeError("LLM response did not contain parseable JSON after retries; raw quarantined: " + "; ".join(errors))

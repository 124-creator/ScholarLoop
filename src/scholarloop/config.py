"""Runtime configuration for ScholarLoop.

Loads LLM endpoint credentials from secrets/llm.env.local into os.environ at
import time. The secrets file is read-only input: values are never printed,
written to reports, or copied elsewhere.
"""
from __future__ import annotations

import os
from pathlib import Path

REQUIRED_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
OPTIONAL_ENV = ("HF_TOKEN", "HF_ACCESS_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN")
ROOT = Path(__file__).resolve().parents[2]
SECRETS_FILE = ROOT / "secrets" / "llm.env.local"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    if key not in REQUIRED_ENV and key not in OPTIONAL_ENV:
        return None
    return key, value


def load_local_llm_env() -> dict[str, bool]:
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if value and not os.environ.get(key):
                os.environ[key] = value
    return {key: bool(os.environ.get(key)) for key in REQUIRED_ENV}


PRESENT = load_local_llm_env()


def require_llm_env() -> None:
    missing = [key for key, present in PRESENT.items() if not present]
    if missing:
        raise RuntimeError("Missing required LLM env vars: " + ", ".join(missing))

from __future__ import annotations

import importlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent


def load_env(path: Path | None = None):
    env_path = path or BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(key: str, default: Any = None):
    value = os.environ.get(key)
    if value is None:
        return default
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    return value


@lru_cache(maxsize=None)
def config(key: str, default: Any = None):
    namespace, _, item = key.partition(".")
    if not namespace or not item:
        return default
    try:
        module = importlib.import_module(f"config.{namespace}")
    except ModuleNotFoundError:
        return default
    return getattr(module, item.upper(), default)

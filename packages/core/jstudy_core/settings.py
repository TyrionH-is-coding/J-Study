from __future__ import annotations

import os
from pathlib import Path


DEFAULT_API_KEY_ENV = "SILICONFLOW_API_KEY"


def read_api_key(path: Path | None, env_var: str = DEFAULT_API_KEY_ENV) -> str:
    env_key = os.getenv(env_var, "").strip()
    if env_key:
        return env_key

    if path is None:
        raise RuntimeError(f"{env_var} is not set and no API key file was provided")
    if not path.exists():
        raise RuntimeError(f"{env_var} is not set and API key file was not found: {path}")

    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"API key file is empty: {path}")
    return key

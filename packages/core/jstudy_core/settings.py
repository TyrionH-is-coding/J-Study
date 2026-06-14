from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from packages.core.jstudy_core.providers import DEFAULT_CHAT_MODEL, DEFAULT_EMBED_MODEL


DEFAULT_API_KEY_ENV = "SILICONFLOW_API_KEY"
DEFAULT_API_KEY_FILE_ENV = "SILICONFLOW_API_KEY_FILE"
JOBS_DIR_ENV = "JSTUDY_JOBS_DIR"
SOUL_PATH_ENV = "JSTUDY_SOUL_PATH"
MNEMONICS_PATH_ENV = "JSTUDY_MNEMONICS_PATH"
MAX_PDF_BYTES_ENV = "JSTUDY_MAX_PDF_BYTES"
DEFAULT_MAX_PDF_BYTES = 50 * 1024 * 1024


def env_path(name: str, default: Path | None) -> Path | None:
    value = os.getenv(name, "").strip()
    if value:
        return Path(value)
    return default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than 0")
    return parsed


@dataclass(frozen=True)
class RuntimeSettings:
    project_root: Path
    jobs_root: Path
    soul_path: Path
    mnemonics_path: Path
    api_key_path: Path | None
    chat_model: str
    embed_model: str
    max_pdf_bytes: int = DEFAULT_MAX_PDF_BYTES

    @classmethod
    def from_env(cls, project_root: Path, jobs_root: Path | None = None) -> "RuntimeSettings":
        return cls(
            project_root=project_root,
            jobs_root=jobs_root or env_path(JOBS_DIR_ENV, project_root / "web_jobs"),
            soul_path=env_path(SOUL_PATH_ENV, project_root / "soul.md"),
            mnemonics_path=env_path(MNEMONICS_PATH_ENV, project_root / "mnemonics.md"),
            api_key_path=env_path(DEFAULT_API_KEY_FILE_ENV, project_root / "siliconflow api key.txt"),
            chat_model=os.getenv("SILICONFLOW_CHAT_MODEL", DEFAULT_CHAT_MODEL).strip() or DEFAULT_CHAT_MODEL,
            embed_model=os.getenv("SILICONFLOW_EMBED_MODEL", DEFAULT_EMBED_MODEL).strip() or DEFAULT_EMBED_MODEL,
            max_pdf_bytes=env_int(MAX_PDF_BYTES_ENV, DEFAULT_MAX_PDF_BYTES),
        )


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

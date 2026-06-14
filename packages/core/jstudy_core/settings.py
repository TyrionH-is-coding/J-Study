from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    def readiness(self) -> dict[str, Any]:
        checks = [
            self._jobs_root_check(),
            self._file_check("soul_path", self.soul_path),
            self._file_check("mnemonics_path", self.mnemonics_path),
            self._api_key_check(),
            self._max_pdf_bytes_check(),
        ]
        status = "ready" if all(check["status"] == "ok" for check in checks) else "degraded"
        return {"status": status, "checks": checks}

    def _jobs_root_check(self) -> dict[str, str]:
        try:
            self.jobs_root.mkdir(parents=True, exist_ok=True)
            probe = self.jobs_root / ".readiness-check"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            return {
                "name": "jobs_root",
                "status": "error",
                "detail": f"jobs directory is not writable: {exc}",
            }
        return {"name": "jobs_root", "status": "ok", "detail": str(self.jobs_root)}

    def _file_check(self, name: str, path: Path) -> dict[str, str]:
        if not path.is_file():
            return {"name": name, "status": "error", "detail": f"file not found: {path}"}
        return {"name": name, "status": "ok", "detail": str(path)}

    def _api_key_check(self) -> dict[str, str]:
        try:
            read_api_key(self.api_key_path)
        except RuntimeError as exc:
            return {"name": "api_key", "status": "error", "detail": str(exc)}
        source = DEFAULT_API_KEY_ENV if os.getenv(DEFAULT_API_KEY_ENV, "").strip() else str(self.api_key_path)
        return {"name": "api_key", "status": "ok", "detail": source}

    def _max_pdf_bytes_check(self) -> dict[str, str]:
        if self.max_pdf_bytes <= 0:
            return {
                "name": "max_pdf_bytes",
                "status": "error",
                "detail": f"{MAX_PDF_BYTES_ENV} must be greater than 0",
            }
        return {"name": "max_pdf_bytes", "status": "ok", "detail": str(self.max_pdf_bytes)}


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

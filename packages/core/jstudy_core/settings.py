from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from packages.core.jstudy_core.admin_settings import (
    DEFAULT_SETTINGS_DIR_NAME,
    AdminSettingsService,
    active_content_pack,
    active_model,
    active_profile,
)
from packages.core.jstudy_core.documents.mineru_client import MinerUClientConfig
from packages.core.jstudy_core.providers import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBED_MODEL,
    SILICONFLOW_BASE_URL,
    probe_siliconflow_provider,
)
from packages.retrieval.hybrid import RagConfig


DEFAULT_API_KEY_ENV = "SILICONFLOW_API_KEY"
DEFAULT_API_KEY_FILE_ENV = "SILICONFLOW_API_KEY_FILE"
SETTINGS_DIR_ENV = "JSTUDY_SETTINGS_DIR"
JOBS_DIR_ENV = "JSTUDY_JOBS_DIR"
SOUL_PATH_ENV = "JSTUDY_SOUL_PATH"
MNEMONICS_PATH_ENV = "JSTUDY_MNEMONICS_PATH"
MAX_PDF_BYTES_ENV = "JSTUDY_MAX_PDF_BYTES"
MAX_PDFS_ENV = "JSTUDY_MAX_PDFS"
MAX_TOTAL_UPLOAD_BYTES_ENV = "JSTUDY_MAX_TOTAL_UPLOAD_BYTES"
MAX_OUTLINE_BYTES_ENV = "JSTUDY_MAX_OUTLINE_BYTES"
QUEUE_CAPACITY_ENV = "JSTUDY_QUEUE_CAPACITY"
USER_ACTIVE_JOB_LIMIT_ENV = "JSTUDY_USER_ACTIVE_JOB_LIMIT"
WORKER_POLL_SECONDS_ENV = "JSTUDY_WORKER_POLL_SECONDS"
WORKER_LEASE_SECONDS_ENV = "JSTUDY_WORKER_LEASE_SECONDS"
WORKER_MAX_ATTEMPTS_ENV = "JSTUDY_WORKER_MAX_ATTEMPTS"
GENERATION_MAX_CONCURRENCY_ENV = "JSTUDY_GENERATION_MAX_CONCURRENCY"
JOB_RETENTION_HOURS_ENV = "JSTUDY_JOB_RETENTION_HOURS"
JSTUDY_DATABASE_URL_ENV = "JSTUDY_DATABASE_URL"
DATABASE_URL_ENV = "DATABASE_URL"
SESSION_SECRET_ENV = "JSTUDY_SESSION_SECRET"
COOKIE_SECURE_ENV = "JSTUDY_COOKIE_SECURE"
COOKIE_NAME_ENV = "JSTUDY_SESSION_COOKIE_NAME"
INVITE_REQUIRED_ENV = "JSTUDY_INVITE_REQUIRED"
MINERU_API_BASE_URL_ENV = "MINERU_API_BASE_URL"
MINERU_API_TOKEN_ENV = "MINERU_API_TOKEN"
MINERU_MODEL_VERSION_ENV = "MINERU_MODEL_VERSION"
MINERU_LANGUAGE_ENV = "MINERU_LANGUAGE"
MINERU_POLL_INTERVAL_SECONDS_ENV = "MINERU_POLL_INTERVAL_SECONDS"
MINERU_DEADLINE_SECONDS_ENV = "MINERU_DEADLINE_SECONDS"
MINERU_MAX_RESULT_BYTES_ENV = "MINERU_MAX_RESULT_BYTES"
DEFAULT_MAX_PDF_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PDFS = 20
DEFAULT_MAX_TOTAL_UPLOAD_BYTES = 300 * 1024 * 1024
DEFAULT_MAX_OUTLINE_BYTES = 5 * 1024 * 1024
DEFAULT_QUEUE_CAPACITY = 100
DEFAULT_USER_ACTIVE_JOB_LIMIT = 3
DEFAULT_WORKER_POLL_SECONDS = 1
DEFAULT_WORKER_LEASE_SECONDS = 300
DEFAULT_WORKER_MAX_ATTEMPTS = 2
DEFAULT_GENERATION_MAX_CONCURRENCY = 3
ProviderProbe = Callable[[str, str, str], dict[str, Any]]


def env_path(name: str, default: Path | None) -> Path | None:
    value = os.getenv(name, "").strip()
    if value:
        return Path(value)
    return default


def env_text(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or str(default).strip()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than 0")
    return parsed


def env_nonnegative_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    parsed = float(value)
    if parsed < 0:
        raise RuntimeError(f"{name} must be greater than or equal to 0")
    return parsed


def env_nonnegative_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    parsed = int(value)
    if parsed < 0:
        raise RuntimeError(f"{name} must be greater than or equal to 0")
    return parsed


def env_bounded_int(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be an integer from {minimum} to {maximum}"
        ) from exc
    if not minimum <= parsed <= maximum:
        raise RuntimeError(
            f"{name} must be an integer from {minimum} to {maximum}"
        )
    return parsed


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false")


@dataclass(frozen=True)
class RuntimeSettings:
    project_root: Path
    jobs_root: Path
    soul_path: Path
    mnemonics_path: Path
    api_key_path: Path | None
    chat_model: str
    embed_model: str
    admin_settings_dir: Path | None = None
    api_key: str = ""
    chat_base_url: str = SILICONFLOW_BASE_URL
    embed_base_url: str = SILICONFLOW_BASE_URL
    rag_config: RagConfig = field(default_factory=RagConfig)
    # parser_config and parser_profiles_config remain for the current pipeline only.
    parser_config: dict[str, Any] = field(default_factory=dict)
    mineru_config: MinerUClientConfig = field(default_factory=MinerUClientConfig)
    mineru_api_token: str = ""
    content_pack: dict[str, Any] = field(default_factory=dict)
    content_pack_config: dict[str, Any] = field(default_factory=dict)
    default_scenario_id: str = "medicine-default"
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    parser_profiles_config: dict[str, Any] = field(default_factory=dict)
    search_config: dict[str, Any] = field(default_factory=dict)
    max_pdfs: int = DEFAULT_MAX_PDFS
    max_pdf_bytes: int = DEFAULT_MAX_PDF_BYTES
    max_total_upload_bytes: int = DEFAULT_MAX_TOTAL_UPLOAD_BYTES
    max_outline_bytes: int = DEFAULT_MAX_OUTLINE_BYTES
    queue_capacity: int = DEFAULT_QUEUE_CAPACITY
    user_active_job_limit: int = DEFAULT_USER_ACTIVE_JOB_LIMIT
    worker_poll_seconds: int = DEFAULT_WORKER_POLL_SECONDS
    worker_lease_seconds: int = DEFAULT_WORKER_LEASE_SECONDS
    worker_max_attempts: int = DEFAULT_WORKER_MAX_ATTEMPTS
    generation_max_concurrency: int = DEFAULT_GENERATION_MAX_CONCURRENCY
    job_retention_hours: int = 0
    database_url: str = ""
    session_secret: str = "dev-session-secret"
    cookie_secure: bool = False
    session_cookie_name: str = "jstudy_session"
    invite_required: bool = True

    @classmethod
    def from_env(cls, project_root: Path, jobs_root: Path | None = None) -> "RuntimeSettings":
        settings_dir = env_path(SETTINGS_DIR_ENV, project_root / DEFAULT_SETTINGS_DIR_NAME)
        admin_settings = AdminSettingsService(settings_dir)
        catalog = admin_settings.load_model_catalog()
        runtime = admin_settings.load_runtime()
        content = admin_settings.load_content_pack()
        pack = active_content_pack(content)
        llm_profile = active_profile(catalog, "llm") or {}
        llm_model = active_model(catalog, "llm") or {}
        embedding_profile = active_profile(catalog, "embedding") or {}
        embedding_model = active_model(catalog, "embedding") or {}
        search_profile = active_profile(catalog, "search") or {}
        mineru_runtime = runtime["parser"]["mineru"]
        mineru_config = MinerUClientConfig(
            api_base_url=env_text(
                MINERU_API_BASE_URL_ENV,
                str(mineru_runtime["api_base_url"]),
            )
            or "https://mineru.net",
            model_version=env_text(
                MINERU_MODEL_VERSION_ENV,
                str(mineru_runtime["model_version"]),
            )
            or "vlm",
            language=env_text(
                MINERU_LANGUAGE_ENV,
                str(mineru_runtime["language"]),
            )
            or "ch",
            enable_table=bool(mineru_runtime["enable_table"]),
            enable_formula=bool(mineru_runtime["enable_formula"]),
            is_ocr=bool(mineru_runtime["is_ocr"]),
            poll_interval_seconds=env_nonnegative_float(
                MINERU_POLL_INTERVAL_SECONDS_ENV,
                float(mineru_runtime["poll_interval_seconds"]),
            ),
            deadline_seconds=float(
                env_int(MINERU_DEADLINE_SECONDS_ENV, int(mineru_runtime["deadline_seconds"]))
            ),
            max_result_bytes=env_int(
                MINERU_MAX_RESULT_BYTES_ENV,
                int(mineru_runtime["max_result_bytes"]),
            ),
        )
        mineru_api_token = env_text(
            MINERU_API_TOKEN_ENV,
            str(mineru_runtime.get("api_token") or ""),
        )
        parser_config = dict(runtime["parser"])
        parser_config["mineru"] = {
            **mineru_runtime,
            "api_base_url": mineru_config.api_base_url,
            "api_token": mineru_api_token,
            "model_version": mineru_config.model_version,
            "language": mineru_config.language,
            "enable_table": mineru_config.enable_table,
            "enable_formula": mineru_config.enable_formula,
            "is_ocr": mineru_config.is_ocr,
            "poll_interval_seconds": mineru_config.poll_interval_seconds,
            "deadline_seconds": mineru_config.deadline_seconds,
            "max_result_bytes": mineru_config.max_result_bytes,
        }
        api_key_path = _catalog_path(project_root, llm_profile.get("api_key_path"))
        if api_key_path is None:
            api_key_path = project_root / "siliconflow api key.txt"
        resolved_jobs_root = jobs_root or env_path(JOBS_DIR_ENV, project_root / "web_jobs")
        database_url = os.getenv(JSTUDY_DATABASE_URL_ENV, "").strip()
        if not database_url:
            database_url = os.getenv(DATABASE_URL_ENV, "").strip()
        if not database_url:
            database_url = f"sqlite:///{(resolved_jobs_root / 'jstudy.db').as_posix()}"

        return cls(
            project_root=project_root,
            jobs_root=resolved_jobs_root,
            soul_path=env_path(SOUL_PATH_ENV, _project_path(project_root, pack.get("soul_path"), "soul.md")),
            mnemonics_path=env_path(
                MNEMONICS_PATH_ENV,
                _project_path(project_root, pack.get("mnemonics_path"), "mnemonics.md"),
            ),
            api_key_path=env_path(DEFAULT_API_KEY_FILE_ENV, api_key_path),
            chat_model=env_text(
                "SILICONFLOW_CHAT_MODEL",
                str(llm_model.get("model") or DEFAULT_CHAT_MODEL),
            )
            or DEFAULT_CHAT_MODEL,
            embed_model=env_text(
                "SILICONFLOW_EMBED_MODEL",
                str(embedding_model.get("model") or DEFAULT_EMBED_MODEL),
            )
            or DEFAULT_EMBED_MODEL,
            admin_settings_dir=settings_dir,
            api_key=str(llm_profile.get("api_key") or embedding_profile.get("api_key") or "").strip(),
            chat_base_url=str(llm_profile.get("base_url") or SILICONFLOW_BASE_URL).strip()
            or SILICONFLOW_BASE_URL,
            embed_base_url=str(embedding_profile.get("base_url") or SILICONFLOW_BASE_URL).strip()
            or SILICONFLOW_BASE_URL,
            rag_config=RagConfig(**runtime["rag"]),
            parser_config=parser_config,
            mineru_config=mineru_config,
            mineru_api_token=mineru_api_token,
            content_pack=pack,
            content_pack_config=content,
            default_scenario_id=str(content.get("default_scenario_id") or content.get("active_pack_id") or "medicine-default"),
            scenarios=list(content.get("scenarios", [])),
            parser_profiles_config=dict(runtime.get("parser_profiles", {})),
            search_config=search_profile,
            max_pdfs=env_int(MAX_PDFS_ENV, DEFAULT_MAX_PDFS),
            max_pdf_bytes=env_int(MAX_PDF_BYTES_ENV, runtime["jobs"]["max_pdf_bytes"]),
            max_total_upload_bytes=env_int(
                MAX_TOTAL_UPLOAD_BYTES_ENV,
                DEFAULT_MAX_TOTAL_UPLOAD_BYTES,
            ),
            max_outline_bytes=env_int(
                MAX_OUTLINE_BYTES_ENV,
                DEFAULT_MAX_OUTLINE_BYTES,
            ),
            queue_capacity=env_int(QUEUE_CAPACITY_ENV, DEFAULT_QUEUE_CAPACITY),
            user_active_job_limit=env_int(
                USER_ACTIVE_JOB_LIMIT_ENV,
                DEFAULT_USER_ACTIVE_JOB_LIMIT,
            ),
            worker_poll_seconds=env_int(
                WORKER_POLL_SECONDS_ENV,
                DEFAULT_WORKER_POLL_SECONDS,
            ),
            worker_lease_seconds=env_int(
                WORKER_LEASE_SECONDS_ENV,
                DEFAULT_WORKER_LEASE_SECONDS,
            ),
            worker_max_attempts=env_int(
                WORKER_MAX_ATTEMPTS_ENV,
                DEFAULT_WORKER_MAX_ATTEMPTS,
            ),
            generation_max_concurrency=env_bounded_int(
                GENERATION_MAX_CONCURRENCY_ENV,
                DEFAULT_GENERATION_MAX_CONCURRENCY,
                minimum=1,
                maximum=4,
            ),
            job_retention_hours=env_nonnegative_int(
                JOB_RETENTION_HOURS_ENV,
                runtime["jobs"]["job_retention_hours"],
            ),
            database_url=database_url,
            session_secret=os.getenv(SESSION_SECRET_ENV, "dev-session-secret").strip() or "dev-session-secret",
            cookie_secure=env_bool(COOKIE_SECURE_ENV, False),
            session_cookie_name=os.getenv(COOKIE_NAME_ENV, "jstudy_session").strip() or "jstudy_session",
            invite_required=env_bool(INVITE_REQUIRED_ENV, True),
        )

    def readiness(
        self,
        probe_provider: bool = False,
        provider_probe: ProviderProbe | None = None,
    ) -> dict[str, Any]:
        checks = [
            self._jobs_root_check(),
            self._file_check("soul_path", self.soul_path),
            self._file_check("mnemonics_path", self.mnemonics_path),
            self._api_key_check(),
            self._mineru_check(),
            self._max_pdf_bytes_check(),
            self._job_retention_check(),
        ]
        if probe_provider:
            checks.append(self._provider_connectivity_check(provider_probe or probe_siliconflow_provider))
        status = "ready" if all(check["status"] == "ok" for check in checks) else "degraded"
        return {
            "status": status,
            "checks": checks,
            "mineru_configured": bool(self.mineru_api_token),
        }

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
        api_key, source, error = self._effective_credential()
        if not api_key:
            return {
                "name": "api_key",
                "status": "error",
                "detail": error or "API key is missing",
            }
        return {"name": "api_key", "status": "ok", "detail": source}

    def _mineru_check(self) -> dict[str, str]:
        if not self.mineru_api_token.strip():
            return {
                "name": "mineru",
                "status": "error",
                "detail": "MinerU is not configured",
            }
        return {
            "name": "mineru",
            "status": "ok",
            "detail": "MinerU is configured",
        }

    def _max_pdf_bytes_check(self) -> dict[str, str]:
        if self.max_pdf_bytes <= 0:
            return {
                "name": "max_pdf_bytes",
                "status": "error",
                "detail": f"{MAX_PDF_BYTES_ENV} must be greater than 0",
            }
        return {"name": "max_pdf_bytes", "status": "ok", "detail": str(self.max_pdf_bytes)}

    def _job_retention_check(self) -> dict[str, str]:
        if self.job_retention_hours < 0:
            return {
                "name": "job_retention_hours",
                "status": "error",
                "detail": f"{JOB_RETENTION_HOURS_ENV} must be greater than or equal to 0",
            }
        detail = "disabled" if self.job_retention_hours == 0 else f"{self.job_retention_hours} hours"
        return {"name": "job_retention_hours", "status": "ok", "detail": detail}

    def _provider_connectivity_check(self, provider_probe: ProviderProbe) -> dict[str, Any]:
        api_key = self.effective_api_key()
        if not api_key:
            return {"name": "provider_connectivity", "status": "error", "detail": "API key is missing"}

        try:
            return provider_probe(api_key, self.chat_model, self.embed_model)
        except Exception as exc:
            return {"name": "provider_connectivity", "status": "error", "detail": str(exc)[:200]}

    def effective_api_key(self) -> str:
        return self._effective_credential()[0]

    def _effective_credential(self) -> tuple[str, str, str]:
        env_key = os.getenv(DEFAULT_API_KEY_ENV, "").strip()
        if env_key:
            return env_key, DEFAULT_API_KEY_ENV, ""
        env_key_file = os.getenv(DEFAULT_API_KEY_FILE_ENV, "").strip()
        if env_key_file:
            try:
                return (
                    _read_api_key_file(Path(env_key_file)),
                    DEFAULT_API_KEY_FILE_ENV,
                    "",
                )
            except RuntimeError as exc:
                return "", DEFAULT_API_KEY_FILE_ENV, str(exc)
        if self.api_key:
            return self.api_key, "admin settings", ""
        try:
            return (
                _read_api_key_file(self.api_key_path),
                str(self.api_key_path),
                "",
            )
        except RuntimeError as exc:
            return "", str(self.api_key_path or ""), str(exc)


RuntimeSettingsProvider = Callable[[], RuntimeSettings]


def load_runtime_settings_snapshot(
    initial: RuntimeSettings,
    provider: RuntimeSettingsProvider,
) -> RuntimeSettings:
    current = provider()
    if current.database_url != initial.database_url:
        raise RuntimeError("runtime settings cannot change database_url")
    if current.jobs_root.resolve() != initial.jobs_root.resolve():
        raise RuntimeError("runtime settings cannot change jobs_root")
    return current


def _project_path(project_root: Path, value: Any, default: str) -> Path:
    text = str(value or default).strip() or default
    path = Path(text)
    if path.is_absolute():
        return path
    return project_root / path


def _catalog_path(project_root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return project_root / path


def read_api_key(path: Path | None, env_var: str = DEFAULT_API_KEY_ENV) -> str:
    env_key = os.getenv(env_var, "").strip()
    if env_key:
        return env_key

    return _read_api_key_file(path, missing_prefix=f"{env_var} is not set and ")


def _read_api_key_file(
    path: Path | None,
    *,
    missing_prefix: str = "",
) -> str:
    if path is None:
        raise RuntimeError(f"{missing_prefix}no API key file was provided")
    if not path.exists():
        raise RuntimeError(f"{missing_prefix}API key file was not found: {path}")

    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"API key file is empty: {path}")
    return key

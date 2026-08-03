from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable

import fitz
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from apps.api.jstudy_api.admin_ui import ADMIN_SETTINGS_HTML
from apps.api.jstudy_api.ui import INDEX_HTML

from packages.core.jstudy_core.admin_settings import AdminSettingsService
from packages.core.jstudy_core.auth_db import create_application_tables, create_auth_engine
from packages.core.jstudy_core.auth_models import InviteCode, InviteCodeUse, User
from packages.core.jstudy_core.auth_service import (
    AuthService,
    AuthServiceError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
    InviteCodeExistsError,
)
from packages.core.jstudy_core.job_system import (
    AdmissionError,
    ArtifactKind,
    ArtifactSnapshot,
    JobAdmissionRequest,
    JobRepository,
    JobService,
    JobSnapshot,
    JobSourceSnapshot,
    public_status,
    resolve_job_path,
)
from packages.core.jstudy_core.courseware import (
    CoursewareManifestV1,
    CoverageLedgerV1,
    LearningMapV1,
    validate_courseware_coordination,
    validate_manifest_snapshot,
)
from packages.core.jstudy_core.scenario_router import ScenarioRoutingError, resolve_scenario
from packages.core.jstudy_core.materials.models import (
    LegacyMaterialPackageV1,
    MaterialPackageV2,
)
from packages.core.jstudy_core.materials.validation import (
    read_material_package_payload,
    validate_material_package,
)
from packages.core.jstudy_core.settings import (
    RuntimeSettings,
    RuntimeSettingsProvider,
    load_runtime_settings_snapshot,
)
from packages.core.jstudy_core.storage import read_json

ProviderProbe = Callable[[str, str, str], dict[str, Any]]


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT = PROJECT_ROOT
NO_STORE_CACHE_CONTROL = "no-store"
PRIVATE_CACHE_CONTROL = "private, max-age=0, must-revalidate"
ADMIN_TOKEN_ENV = "JSTUDY_ADMIN_TOKEN"
TRACE_PATH_KEYS = {"pdf", "pdfs", "outline", "embedding_cache"}
SYNC_ARTIFACT_MAX_BYTES = 32 * 1024 * 1024
PARSER_COMPATIBILITY_ALIASES = {"", "fast", "quality"}


def private_cache_headers() -> dict[str, str]:
    return {"Cache-Control": PRIVATE_CACHE_CONTROL}


def set_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = NO_STORE_CACHE_CONTROL


def set_private_cache(response: Response) -> None:
    response.headers["Cache-Control"] = PRIVATE_CACHE_CONTROL


def public_readiness_payload(readiness: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for raw_check in readiness.get("checks", []):
        status = str(raw_check.get("status") or "error")
        checks.append(
            {
                "name": str(raw_check.get("name") or ""),
                "status": status,
                "detail": "available" if status == "ok" else "unavailable",
            }
        )
    return {
        "status": str(readiness.get("status") or "degraded"),
        "checks": checks,
        "mineru_configured": bool(readiness.get("mineru_configured")),
    }


def public_trace_payload(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower()
    path_field = (
        normalized_key in TRACE_PATH_KEYS
        or normalized_key == "path"
        or normalized_key.endswith("_path")
        or normalized_key.endswith("_paths")
    )
    if isinstance(value, dict):
        return {
            item_key: public_trace_payload(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [public_trace_payload(item, key=key) for item in value]
    if isinstance(value, str):
        text = value.strip()
        windows_path = PureWindowsPath(text)
        if (
            path_field
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or PurePosixPath(text).is_absolute()
        ):
            return "[redacted]"
    return value


def project_path(project_root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else project_root / path


def pdf_info_payload(path: Path, source_id: str = "") -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    with fitz.open(str(path)) as doc:
        pages = [
            {
                "page": index + 1,
                "width": round(page.rect.width, 2),
                "height": round(page.rect.height, 2),
            }
            for index, page in enumerate(doc)
        ]
    payload = {"page_count": len(pages), "pages": pages}
    if source_id:
        payload["source_id"] = source_id
    return payload


def pdf_page_png_response(path: Path, page_no: int) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    with fitz.open(str(path)) as doc:
        if page_no < 1 or page_no > len(doc):
            raise HTTPException(status_code=404, detail="PDF page not found")
        page = doc.load_page(page_no - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        return Response(
            content=pixmap.tobytes("png"),
            media_type="image/png",
            headers=private_cache_headers(),
        )

def require_admin(request: Request) -> None:
    expected = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        return
    if not is_admin_request(request):
        raise HTTPException(status_code=401, detail="Admin token required")


def is_admin_request(request: Request) -> bool:
    expected = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        return False
    auth = request.headers.get("authorization", "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    query = request.query_params.get("admin_token", "").strip()
    return expected in {bearer, query}


def set_session_cookie(response: Response, runtime: RuntimeSettings, token: str) -> None:
    response.set_cookie(
        runtime.session_cookie_name,
        token,
        httponly=True,
        secure=runtime.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, runtime: RuntimeSettings) -> None:
    response.delete_cookie(runtime.session_cookie_name, path="/", samesite="lax")


def session_token_from_request(request: Request, runtime: RuntimeSettings) -> str:
    return request.cookies.get(runtime.session_cookie_name, "").strip()


def user_payload(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "email_verified": user.email_verified}


def invite_payload(invite: InviteCode, usage_count: int = 0) -> dict[str, Any]:
    return {
        "id": invite.id,
        "code": invite.code,
        "label": invite.label,
        "enabled": invite.enabled,
        "created_at": invite.created_at.isoformat(),
        "updated_at": invite.updated_at.isoformat(),
        "disabled_at": invite.disabled_at.isoformat() if invite.disabled_at else None,
        "usage_count": usage_count,
    }


def invite_use_payload(item: InviteCodeUse) -> dict[str, Any]:
    return {
        "id": item.id,
        "invite_code_id": item.invite_code_id,
        "user_id": item.user_id,
        "email": item.email,
        "used_at": item.used_at.isoformat(),
    }


def create_app(
    base_dir: Path | None = None,
    settings: RuntimeSettings | None = None,
    provider_probe: ProviderProbe | None = None,
    job_repository: JobRepository | None = None,
    job_service: JobService | None = None,
    settings_provider: RuntimeSettingsProvider | None = None,
) -> FastAPI:
    runtime = settings or RuntimeSettings.from_env(ROOT, jobs_root=base_dir)
    jobs_root = base_dir or runtime.jobs_root
    jobs_root.mkdir(parents=True, exist_ok=True)
    admin_settings = AdminSettingsService(
        runtime.admin_settings_dir or runtime.project_root / "data" / "settings"
    )
    database_url = runtime.database_url or f"sqlite:///{(jobs_root / 'jstudy.db').as_posix()}"
    initial_runtime = runtime

    if settings_provider is not None:
        load_runtime = settings_provider
    elif settings is None or runtime.admin_settings_dir is not None:
        load_runtime = lambda: RuntimeSettings.from_env(
            initial_runtime.project_root,
            jobs_root=jobs_root,
        )
    else:
        load_runtime = lambda: initial_runtime

    owns_engine = job_repository is None and job_service is None
    if job_service is not None:
        if job_repository is not None and job_service.repository is not job_repository:
            raise ValueError("job_service and job_repository must use the same repository")
        repository = job_service.repository
    else:
        repository = job_repository or JobRepository(create_auth_engine(database_url))
    application_engine = repository.engine
    create_application_tables(application_engine)
    durable_service = job_service or JobService(
        repository,
        runtime,
        settings_provider=load_runtime,
    )
    auth_service = AuthService(application_engine, invite_required=runtime.invite_required)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if owns_engine:
                application_engine.dispose()

    app = FastAPI(title="J Study MVP", lifespan=lifespan)
    app.state.job_repository = repository
    app.state.job_service = durable_service

    def refresh_runtime() -> None:
        nonlocal runtime
        runtime = load_runtime_settings_snapshot(initial_runtime, load_runtime)

    def routing_content_config() -> dict[str, Any]:
        return runtime.content_pack_config or admin_settings.load_content_pack()

    def application_readiness(
        *,
        probe_provider: bool = False,
    ) -> dict[str, Any]:
        payload = public_readiness_payload(
            runtime.readiness(
                probe_provider=probe_provider,
                provider_probe=provider_probe,
            )
        )
        database_available = repository.check_connection()
        payload["checks"].append(
            {
                "name": "database",
                "status": "ok" if database_available else "error",
                "detail": (
                    "database available"
                    if database_available
                    else "database unavailable"
                ),
            }
        )
        if not database_available:
            payload["status"] = "degraded"
        return payload

    def current_user_or_401(request: Request) -> User:
        token = session_token_from_request(request, runtime)
        user = auth_service.get_user_by_token(token) if token else None
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    def job_or_404(job_id: str, current_user: User) -> JobSnapshot:
        job = repository.get_owned(job_id, current_user.id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    def source_files(job: JobSnapshot) -> list[dict[str, Any]]:
        return [
            {
                "source_id": source.source_id,
                "file_name": source.original_filename,
                "original_filename": source.original_filename,
                "display_title": source.display_title,
                "display_order": source.display_order,
                "page_count": source.page_count,
            }
            for source in repository.list_sources(job.id)
        ]

    def source_or_404(job: JobSnapshot, source_id: str) -> JobSourceSnapshot:
        for source in repository.list_sources(job.id):
            if source.source_id == source_id:
                return source
        raise HTTPException(status_code=404, detail="Source PDF not found")

    def resolved_source_path(source: JobSourceSnapshot) -> Path:
        try:
            path = resolve_job_path(jobs_root, source.relative_path)
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="PDF not found")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="PDF not found")
        return path

    def source_pdf_path(job: JobSnapshot, source_id: str) -> Path:
        return resolved_source_path(source_or_404(job, source_id))

    def artifact_map(job: JobSnapshot) -> dict[ArtifactKind, ArtifactSnapshot]:
        return {
            artifact.kind: artifact
            for artifact in repository.list_artifacts(job.id)
        }

    def ready_output_path(job: JobSnapshot, kind: ArtifactKind, detail: str) -> Path:
        artifact = artifact_map(job).get(kind)
        if artifact is None:
            raise HTTPException(status_code=404, detail=detail)
        try:
            path = resolve_job_path(jobs_root, artifact.relative_path)
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail=detail)
        if not path.is_file():
            raise HTTPException(status_code=404, detail=detail)
        return path

    def read_sync_artifact(
        path: Path,
        model: type[BaseModel],
        *,
        expected_manifest_id: str,
        expected_sha256: str | None = None,
    ) -> BaseModel:
        with path.open("rb") as handle:
            payload = handle.read(SYNC_ARTIFACT_MAX_BYTES + 1)
        if len(payload) > SYNC_ARTIFACT_MAX_BYTES:
            raise ValueError("synchronization artifact is too large")
        if (
            expected_sha256 is not None
            and hashlib.sha256(payload).hexdigest() != expected_sha256
        ):
            raise ValueError("synchronization artifact hash mismatch")
        parsed = model.model_validate_json(payload)
        manifest_id = getattr(parsed, "manifest_id", None)
        if manifest_id != expected_manifest_id:
            raise ValueError("synchronization artifact identity mismatch")
        if isinstance(parsed, CoursewareManifestV1) and parsed.job_id != expected_manifest_id:
            raise ValueError("courseware manifest job identity mismatch")
        return parsed

    def validate_job_manifest(
        job: JobSnapshot,
        manifest: CoursewareManifestV1,
    ) -> None:
        validate_manifest_snapshot(
            manifest,
            job=job,
            sources=repository.list_sources(job.id),
        )

    def read_validated_sync_bundle(
        job: JobSnapshot,
    ) -> tuple[CoursewareManifestV1, LearningMapV1, CoverageLedgerV1]:
        artifacts = artifact_map(job)
        manifest = read_sync_artifact(
            ready_output_path(
                job,
                ArtifactKind.MANIFEST,
                "Courseware manifest is not ready",
            ),
            CoursewareManifestV1,
            expected_manifest_id=job.id,
            expected_sha256=artifacts[ArtifactKind.MANIFEST].sha256,
        )
        learning_map = read_sync_artifact(
            ready_output_path(
                job,
                ArtifactKind.LEARNING_MAP,
                "Learning map is not ready",
            ),
            LearningMapV1,
            expected_manifest_id=job.id,
            expected_sha256=artifacts[ArtifactKind.LEARNING_MAP].sha256,
        )
        coverage = read_sync_artifact(
            ready_output_path(
                job,
                ArtifactKind.COVERAGE,
                "Coverage ledger is not ready",
            ),
            CoverageLedgerV1,
            expected_manifest_id=job.id,
            expected_sha256=artifacts[ArtifactKind.COVERAGE].sha256,
        )
        validate_job_manifest(job, manifest)
        validate_courseware_coordination(
            manifest,
            learning_map,
            coverage,
            source_page_counts={
                source.source_id: source.page_count
                for source in repository.list_sources(job.id)
            },
        )
        return manifest, learning_map, coverage

    def quality_payload(job: JobSnapshot) -> dict[str, Any]:
        artifact = artifact_map(job).get(ArtifactKind.QUALITY)
        if artifact is None:
            return {}
        try:
            path = resolve_job_path(jobs_root, artifact.relative_path)
            return read_json(path) if path.is_file() else {}
        except (OSError, ValueError):
            return {}

    def generation_file_or_503(path: Path, label: str) -> Path:
        if not path.is_file():
            raise HTTPException(status_code=503, detail=f"{label} file not found: {path}")
        return path

    def selected_content_paths(scenario: Any) -> dict[str, str]:
        soul_path = None
        if scenario.scenario_id == runtime.default_scenario_id:
            soul_path = runtime.soul_path
        if soul_path is None:
            soul_path = project_path(runtime.project_root, scenario.soul_profile.get("soul_path"))
        if soul_path is None:
            raise HTTPException(
                status_code=503,
                detail=f"Soul profile has no soul_path: {scenario.soul_profile.get('id', '')}",
            )
        mnemonics_path = None
        if scenario.scenario_id == runtime.default_scenario_id:
            mnemonics_path = runtime.mnemonics_path
        if mnemonics_path is None:
            mnemonics_path = (
                project_path(runtime.project_root, scenario.content_pack.get("mnemonics_path"))
                or runtime.mnemonics_path
            )
        return {
            "soul_path": str(generation_file_or_503(soul_path, "Soul profile")),
            "mnemonics_path": str(generation_file_or_503(mnemonics_path, "Knowledge snippet")),
        }

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/admin/settings", response_class=HTMLResponse)
    def admin_settings_page(request: Request) -> str:
        require_admin(request)
        return ADMIN_SETTINGS_HTML

    @app.get("/api/admin/settings")
    def get_admin_settings(request: Request, response: Response) -> dict[str, Any]:
        require_admin(request)
        set_no_store(response)
        return admin_settings.load_public()

    @app.get("/api/admin/invite-codes")
    def list_invite_codes(request: Request, response: Response) -> list[dict[str, Any]]:
        require_admin(request)
        set_no_store(response)
        return [
            invite_payload(invite, usage_count=len(auth_service.list_invite_uses(invite.id)))
            for invite in auth_service.list_invite_codes()
        ]

    @app.post("/api/admin/invite-codes")
    def create_invite_code(
        request: Request,
        response: Response,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        require_admin(request)
        set_no_store(response)
        try:
            invite = auth_service.create_invite_code(
                str(payload.get("code") or ""),
                label=str(payload.get("label") or ""),
            )
        except InviteCodeExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except InvalidInviteCodeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return invite_payload(invite)

    @app.patch("/api/admin/invite-codes/{invite_id}")
    def update_invite_code(
        invite_id: str,
        request: Request,
        response: Response,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        require_admin(request)
        set_no_store(response)
        try:
            if "enabled" in payload:
                invite = auth_service.set_invite_code_enabled(invite_id, bool(payload["enabled"]))
            else:
                invite = next(item for item in auth_service.list_invite_codes() if item.id == invite_id)
        except (InvalidInviteCodeError, StopIteration) as exc:
            raise HTTPException(status_code=404, detail=str(exc) or "Invite code not found")
        return invite_payload(invite, usage_count=len(auth_service.list_invite_uses(invite.id)))

    @app.get("/api/admin/invite-codes/{invite_id}/uses")
    def list_invite_code_uses(invite_id: str, request: Request, response: Response) -> list[dict[str, Any]]:
        require_admin(request)
        set_no_store(response)
        return [invite_use_payload(item) for item in auth_service.list_invite_uses(invite_id)]

    @app.put("/api/admin/settings")
    def update_admin_settings(
        request: Request,
        response: Response,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        require_admin(request)
        set_no_store(response)
        saved = admin_settings.save_public(payload)
        if any(str(item.get("content", "")).strip() for item in saved["mnemonics"]["items"]):
            admin_settings.sync_mnemonics_markdown(runtime.project_root)
        refresh_runtime()
        return admin_settings.load_public()

    @app.post("/api/admin/settings/test/{service_name}")
    def test_admin_setting(
        service_name: str,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        require_admin(request)
        set_no_store(response)
        if service_name in {"llm", "embedding"}:
            check = runtime.readiness(
                probe_provider=True,
                provider_probe=provider_probe,
            )
            checks = {check["name"]: check for check in check["checks"]}
            return checks.get(
                "provider_connectivity",
                {"name": "provider_connectivity", "status": "error", "detail": "probe not available"},
            )
        if service_name == "search":
            search = runtime.search_config
            provider = str(search.get("provider") or "none")
            api_key = str(search.get("api_key") or "")
            base_url = str(search.get("base_url") or "")
            if provider == "none":
                return {"name": "search", "status": "ok", "detail": "search disabled"}
            if provider in {"brave", "tavily", "jina", "perplexity", "serper"} and not api_key:
                return {"name": "search", "status": "error", "detail": f"{provider} requires api_key"}
            if provider == "searxng" and not base_url:
                return {"name": "search", "status": "error", "detail": "searxng requires base_url"}
            return {"name": "search", "status": "ok", "detail": provider}
        raise HTTPException(status_code=404, detail="Unknown settings service")

    @app.post("/api/auth/register")
    def register(payload: dict[str, Any], response: Response) -> dict[str, Any]:
        set_no_store(response)
        try:
            user = auth_service.register(
                str(payload.get("email") or ""),
                str(payload.get("password") or ""),
                str(payload.get("invite_code") or ""),
            )
            token = auth_service.create_session(user.id)
        except DuplicateEmailError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except InvalidInviteCodeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except AuthServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        set_session_cookie(response, runtime, token)
        return user_payload(user)

    @app.post("/api/auth/login")
    def login(payload: dict[str, Any], response: Response) -> dict[str, Any]:
        set_no_store(response)
        try:
            user, token = auth_service.login(
                str(payload.get("email") or ""),
                str(payload.get("password") or ""),
            )
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        set_session_cookie(response, runtime, token)
        return user_payload(user)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, str]:
        set_no_store(response)
        token = session_token_from_request(request, runtime)
        if token:
            auth_service.logout(token)
        clear_session_cookie(response, runtime)
        return {"status": "ok"}

    @app.get("/api/auth/me")
    def me(request: Request, response: Response) -> dict[str, Any]:
        set_no_store(response)
        return user_payload(current_user_or_401(request))

    @app.get("/api/health")
    def health(response: Response) -> dict[str, str]:
        set_no_store(response)
        return {"status": "ok", "service": "jstudy-api"}

    @app.get("/api/readiness")
    def readiness(response: Response, probe_provider: bool = False) -> dict[str, Any]:
        set_no_store(response)
        return {
            "service": "jstudy-api",
            **application_readiness(probe_provider=probe_provider),
        }

    @app.get("/api/options")
    def options(response: Response) -> dict[str, Any]:
        set_no_store(response)
        scenarios = [
            {
                "id": item.get("id", ""),
                "display_name": item.get("display_name", ""),
                "subject": item.get("subject", ""),
            }
            for item in routing_content_config().get("scenarios", [])
            if item.get("enabled", True)
        ]
        return {
            "default_scenario_id": runtime.default_scenario_id,
            "scenarios": scenarios,
            "default_service_mode": "single_courseware",
            "service_modes": [
                {
                    "id": "single_courseware",
                    "display_name": "单课件",
                    "enabled": True,
                },
                {
                    "id": "course_outline",
                    "display_name": "课程大纲",
                    "enabled": True,
                },
                {
                    "id": "multi_courseware",
                    "display_name": "多课件",
                    "enabled": True,
                },
            ],
        }

    @app.post("/api/generate")
    async def generate(
        response: Response,
        request: Request,
        pdf: UploadFile | None = File(None),
        outline: UploadFile | None = File(None),
        pdfs: list[UploadFile] | None = File(None),
        service_mode: str = Form(""),
        scenario_id: str = Form(""),
        parser_profile_id: str = Form(""),
        mode: str = Form(""),
    ) -> dict[str, Any]:
        set_no_store(response)
        current_user = current_user_or_401(request)
        refresh_runtime()
        resolved_service_mode = (service_mode or "").strip() or "single_courseware"
        runtime_readiness = application_readiness()
        if runtime_readiness["status"] != "ready":
            raise HTTPException(
                status_code=503,
                detail=runtime_readiness,
            )

        try:
            scenario = resolve_scenario(routing_content_config(), scenario_id)
        except ScenarioRoutingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        requested_parser_alias = (parser_profile_id or "").strip()
        if requested_parser_alias not in PARSER_COMPATIBILITY_ALIASES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown parser_profile_id: {requested_parser_alias}",
            )

        selected_content_paths(scenario)
        single_pdf = pdf if pdf is not None and pdf.filename else None
        repeated_pdfs = tuple(
            item
            for item in (pdfs or [])
            if item is not None and item.filename
        )
        submitted_outline = (
            outline
            if outline is not None and outline.filename
            else None
        )
        if resolved_service_mode == "single_courseware":
            if repeated_pdfs:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_pdf",
                        "message": "Single courseware accepts only the singular pdf field.",
                    },
                )
            if submitted_outline is not None:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_outline",
                        "message": "Single courseware does not accept an outline.",
                    },
                )
            uploads = (single_pdf,) if single_pdf is not None else ()
        elif resolved_service_mode in {"course_outline", "multi_courseware"}:
            if single_pdf is not None:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_pdf",
                        "message": "This service mode accepts only repeated pdfs fields.",
                    },
                )
            if (
                resolved_service_mode == "multi_courseware"
                and submitted_outline is not None
            ):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_outline",
                        "message": "Multi courseware does not accept an outline.",
                    },
                )
            uploads = repeated_pdfs
        else:
            uploads = ()
        try:
            submission = await durable_service.submit(
                JobAdmissionRequest(
                    owner_user_id=current_user.id,
                    service_mode=resolved_service_mode,
                    scenario_id=scenario.scenario_id,
                    parser_profile_id=requested_parser_alias or "fast",
                    generation_mode=(mode or "").strip() or None,
                    outline=submitted_outline,
                    pdfs=uploads,
                    idempotency_key=(
                        request.headers.get("Idempotency-Key", "").strip()
                        or None
                    ),
                    content_metadata={
                        "scenario": scenario.trace_metadata(),
                        "parser_profile": {
                            "requested_parser_profile_id": requested_parser_alias,
                            "resolved_parser_profile_id": "mineru",
                            "backend": "mineru",
                        },
                    },
                ),
                settings_snapshot=runtime,
            )
        except AdmissionError as exc:
            status_code = {
                "outline_too_large": 413,
                "pdf_too_large": 413,
                "total_upload_too_large": 413,
                "too_many_pdfs": 413,
                "idempotency_conflict": 409,
                "queue_full": 429,
                "user_active_job_limit": 429,
            }.get(exc.code, 400)
            raise HTTPException(
                status_code=status_code,
                detail={"code": exc.code, "message": str(exc)},
            )
        job_id = submission.job.id
        return {
            "job_id": job_id,
            "status": public_status(submission.job.state),
            "status_url": f"/api/jobs/{job_id}",
        }

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_no_store(response)
        job = job_or_404(job_id, current_user_or_401(request))
        return {
            "job_id": job_id,
            "status": public_status(job.state),
            "state": job.state.value,
            "stage": job.state.value,
            "progress": job.progress,
            "attempt_count": job.attempt_count,
            "error_code": job.error_code,
            "error": job.error_message,
            "quality": quality_payload(job),
            "service_mode": job.service_mode,
            "source_files": source_files(job),
            "output_url": f"/api/jobs/{job_id}/output",
            "evidence_url": f"/api/jobs/{job_id}/evidence",
            "evidence_links_url": f"/api/jobs/{job_id}/evidence-links",
            "trace_url": f"/api/jobs/{job_id}/trace",
            "package_url": f"/api/jobs/{job_id}/package",
            "manifest_url": f"/api/jobs/{job_id}/manifest",
            "learning_map_url": f"/api/jobs/{job_id}/learning-map",
            "coverage_url": f"/api/jobs/{job_id}/coverage",
            "export_url": f"/api/jobs/{job_id}/export",
            "pdf_url": f"/api/jobs/{job_id}/pdf",
            "pdf_info_url": f"/api/jobs/{job_id}/pdf-info",
            "pdf_page_url_template": f"/api/jobs/{job_id}/pdf-page/{{page}}.png",
            "pdfs_url": f"/api/jobs/{job_id}/pdfs",
            "source_pdf_url_template": f"/api/jobs/{job_id}/pdfs/{{source_id}}/pdf",
            "source_pdf_info_url_template": f"/api/jobs/{job_id}/pdfs/{{source_id}}/pdf-info",
            "source_pdf_page_url_template": f"/api/jobs/{job_id}/pdfs/{{source_id}}/pdf-page/{{page}}.png",
        }

    @app.get("/api/jobs/{job_id}/output")
    def job_output(job_id: str, request: Request, response: Response) -> dict[str, str]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, ArtifactKind.MARKDOWN, "Output is not ready")
        return {"markdown": path.read_text(encoding="utf-8")}

    @app.get("/api/jobs/{job_id}/evidence")
    def job_evidence(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        evidence_path = ready_output_path(job, ArtifactKind.EVIDENCE, "Evidence is not ready")
        links_path = ready_output_path(job, ArtifactKind.EVIDENCE_LINKS, "Evidence is not ready")
        return {
            "evidence": read_json(evidence_path),
            "evidence_links": read_json(links_path),
        }

    @app.get("/api/jobs/{job_id}/evidence-links")
    def job_evidence_links(job_id: str, request: Request, response: Response) -> Any:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, ArtifactKind.EVIDENCE_LINKS, "Evidence links are not ready")
        return read_json(path)

    @app.get("/api/jobs/{job_id}/trace")
    def job_trace(job_id: str, request: Request, response: Response) -> Any:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, ArtifactKind.TRACE, "Retrieval trace is not ready")
        return public_trace_payload(read_json(path))

    @app.get(
        "/api/jobs/{job_id}/package",
        response_model=MaterialPackageV2 | LegacyMaterialPackageV1,
    )
    def job_package(job_id: str, request: Request, response: Response) -> Any:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, ArtifactKind.PACKAGE, "Material package is not ready")
        try:
            payload = read_material_package_payload(path)
            if payload.get("schema_version") == "material-package.v2":
                package = MaterialPackageV2.model_validate(payload)
                evidence_path = ready_output_path(
                    job,
                    ArtifactKind.EVIDENCE,
                    "Evidence is not ready",
                )
                validate_material_package(
                    package,
                    read_json(evidence_path),
                    [
                        source.source_id
                        for source in repository.list_sources(job.id)
                    ],
                    expected_package_id=job.id,
                    expected_service_mode=job.service_mode,
                )
                return package
            if "schema_version" in payload:
                raise ValueError("unknown material package schema")
            return LegacyMaterialPackageV1.model_validate(payload)
        except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Material package is invalid",
            ) from exc

    @app.get(
        "/api/jobs/{job_id}/manifest",
        response_model=CoursewareManifestV1,
    )
    def job_manifest(
        job_id: str,
        request: Request,
        response: Response,
    ) -> CoursewareManifestV1:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        try:
            manifest, _, _ = read_validated_sync_bundle(job)
            return manifest
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Courseware manifest is invalid",
            ) from exc

    @app.get(
        "/api/jobs/{job_id}/learning-map",
        response_model=LearningMapV1,
    )
    def job_learning_map(
        job_id: str,
        request: Request,
        response: Response,
    ) -> LearningMapV1:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        try:
            _, learning_map, _ = read_validated_sync_bundle(job)
            return learning_map
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Learning map is invalid",
            ) from exc

    @app.get(
        "/api/jobs/{job_id}/coverage",
        response_model=CoverageLedgerV1,
    )
    def job_coverage(
        job_id: str,
        request: Request,
        response: Response,
    ) -> CoverageLedgerV1:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        try:
            _, _, coverage = read_validated_sync_bundle(job)
            return coverage
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Coverage ledger is invalid",
            ) from exc

    @app.get("/api/jobs/{job_id}/export")
    def job_export(job_id: str, request: Request) -> Response:
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, ArtifactKind.MARKDOWN, "Output is not ready")
        return Response(
            content=path.read_bytes(),
            media_type="text/markdown; charset=utf-8",
            headers={
                **private_cache_headers(),
                "Content-Disposition": f'attachment; filename="jstudy-{job_id[:8]}.md"',
            },
        )

    @app.get("/api/jobs/{job_id}/pdfs")
    def job_pdfs(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        return {"source_files": source_files(job)}

    @app.get("/api/jobs/{job_id}/pdfs/{source_id}/pdf")
    def job_source_pdf(job_id: str, source_id: str, request: Request) -> FileResponse:
        job = job_or_404(job_id, current_user_or_401(request))
        source = source_or_404(job, source_id)
        path = resolved_source_path(source)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=source.original_filename,
            headers=private_cache_headers(),
        )

    @app.get("/api/jobs/{job_id}/pdfs/{source_id}/pdf-info")
    def job_source_pdf_info(job_id: str, source_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        return pdf_info_payload(source_pdf_path(job, source_id), source_id=source_id)

    @app.get("/api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page_no}.png")
    def job_source_pdf_page_png(job_id: str, source_id: str, page_no: int, request: Request) -> Response:
        job = job_or_404(job_id, current_user_or_401(request))
        return pdf_page_png_response(source_pdf_path(job, source_id), page_no)

    @app.get("/api/jobs/{job_id}/pdf")
    def job_pdf(job_id: str, request: Request) -> FileResponse:
        job = job_or_404(job_id, current_user_or_401(request))
        source = source_or_404(job, "S001")
        path = resolved_source_path(source)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=source.original_filename,
            headers=private_cache_headers(),
        )

    @app.get("/api/jobs/{job_id}/pdf-info")
    def job_pdf_info(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        return pdf_info_payload(source_pdf_path(job, "S001"))

    @app.get("/api/jobs/{job_id}/pdf-page/{page_no}.png")
    def job_pdf_page_png(job_id: str, page_no: int, request: Request) -> Response:
        job = job_or_404(job_id, current_user_or_401(request))
        return pdf_page_png_response(source_pdf_path(job, "S001"), page_no)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_mvp:app", host="127.0.0.1", port=8765, reload=False)

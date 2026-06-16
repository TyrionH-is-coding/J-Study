from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import inspect
import os
from pathlib import Path
import re
from typing import Any, Callable
import unicodedata
from uuid import uuid4

import fitz
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from apps.api.jstudy_api.admin_ui import ADMIN_SETTINGS_HTML
from apps.api.jstudy_api.ui import INDEX_HTML

from packages.core.jstudy_core.admin_settings import AdminSettingsService
from packages.core.jstudy_core.auth_db import create_auth_engine, create_auth_tables
from packages.core.jstudy_core.auth_models import InviteCode, InviteCodeUse, User
from packages.core.jstudy_core.auth_service import (
    AuthService,
    AuthServiceError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
    InviteCodeExistsError,
)
from packages.core.jstudy_core.jobs import JobRecord, JobStore
from packages.core.jstudy_core.parser_profile_router import (
    ParserProfileRoutingError,
    ParserProfileUnavailable,
    public_parser_profiles,
    resolve_parser_profile,
)
from packages.core.jstudy_core.pipeline import run_mvp
from packages.core.jstudy_core.scenario_router import ScenarioRoutingError, resolve_scenario
from packages.core.jstudy_core.settings import RuntimeSettings
from packages.core.jstudy_core.storage import read_json

Runner = Callable[..., dict[str, Path]]
ProviderProbe = Callable[[str, str, str], dict[str, Any]]


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT = PROJECT_ROOT
NO_STORE_CACHE_CONTROL = "no-store"
PRIVATE_CACHE_CONTROL = "private, max-age=0, must-revalidate"
ADMIN_TOKEN_ENV = "JSTUDY_ADMIN_TOKEN"


def private_cache_headers() -> dict[str, str]:
    return {"Cache-Control": PRIVATE_CACHE_CONTROL}


def set_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = NO_STORE_CACHE_CONTROL


def set_private_cache(response: Response) -> None:
    response.headers["Cache-Control"] = PRIVATE_CACHE_CONTROL


async def save_upload(upload: UploadFile, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await upload.read())


def safe_upload_name(filename: str, default: str) -> str:
    normalized = unicodedata.normalize("NFC", filename or default)
    name = normalized.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    if not name or name in (".", "..") or name.strip("_") == "":
        return default
    return name


def project_path(project_root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else project_root / path


async def save_pdf_upload(upload: UploadFile, target: Path, max_bytes: int) -> None:
    data = await upload.read()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"PDF upload too large: {len(data)} bytes")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def format_job_error(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def filter_runner_kwargs(runner: Runner, kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(runner)
    parameters = signature.parameters.values()
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return kwargs
    allowed = set(signature.parameters)
    return {key: value for key, value in kwargs.items() if key in allowed}


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
    runner: Runner = run_mvp,
    job_store: JobStore | None = None,
    settings: RuntimeSettings | None = None,
    provider_probe: ProviderProbe | None = None,
) -> FastAPI:
    runtime = settings or RuntimeSettings.from_env(ROOT, jobs_root=base_dir)
    jobs_root = base_dir or runtime.jobs_root
    jobs_root.mkdir(parents=True, exist_ok=True)
    jobs = job_store or JobStore(store_path=jobs_root / "jobs.json")
    admin_settings = AdminSettingsService(
        runtime.admin_settings_dir or runtime.project_root / "data" / "settings"
    )
    database_url = runtime.database_url or f"sqlite:///{(jobs_root / 'jstudy.db').as_posix()}"
    auth_engine = create_auth_engine(database_url)
    create_auth_tables(auth_engine)
    auth_service = AuthService(auth_engine, invite_required=runtime.invite_required)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            auth_engine.dispose()

    app = FastAPI(title="J Study MVP", lifespan=lifespan)

    def refresh_runtime() -> None:
        nonlocal runtime
        runtime = RuntimeSettings.from_env(runtime.project_root, jobs_root=jobs_root)

    def cleanup_expired_jobs() -> None:
        if runtime.job_retention_hours <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(hours=runtime.job_retention_hours)
        jobs.cleanup_finished_older_than(cutoff, delete_files=True)

    cleanup_expired_jobs()

    def routing_content_config() -> dict[str, Any]:
        return runtime.content_pack_config or admin_settings.load_content_pack()

    def routing_parser_profiles_config() -> dict[str, Any]:
        return runtime.parser_profiles_config or admin_settings.load_runtime().get("parser_profiles", {})

    def current_user_or_401(request: Request) -> User:
        token = session_token_from_request(request, runtime)
        user = auth_service.get_user_by_token(token) if token else None
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    def job_or_404(job_id: str, current_user: User) -> JobRecord:
        try:
            job = jobs.require(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Job not found")
        owner_user_id = str(job.metadata.get("owner_user_id") or "")
        if not owner_user_id or owner_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    def ready_output_path(job: JobRecord, key: str, detail: str) -> Path:
        path = job.outputs.get(key)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail=detail)
        return path

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

    def run_job(job_id: str) -> None:
        job = jobs.require(job_id)
        jobs.mark_running(job_id)
        try:
            content_paths = job.metadata.get("content_paths", {})
            runner_kwargs = {
                "pdf_path": job.pdf_path,
                "soul_path": Path(str(content_paths.get("soul_path") or runtime.soul_path)),
                "mnemonics_path": Path(str(content_paths.get("mnemonics_path") or runtime.mnemonics_path)),
                "api_key_path": runtime.api_key_path,
                "output_dir": job.output_dir,
                "chat_model": runtime.chat_model,
                "embed_model": runtime.embed_model,
                "output_prefix": "result",
                "rag_config": runtime.rag_config,
                "embedding_cache_path": jobs_root / ".cache" / "embeddings.json",
                "outline_path": job.outline_path,
                "api_key": runtime.api_key or None,
                "embed_api_key": os.getenv("JSTUDY_EMBED_API_KEY", "").strip() or None,
                "chat_base_url": runtime.chat_base_url,
                "embed_base_url": runtime.embed_base_url,
                "parser_backend": job.metadata.get("parser_profile", {}).get("backend", "pymupdf"),
                "routing_metadata": job.metadata,
                "parser_config": runtime.parser_config,
            }
            outputs = runner(
                **filter_runner_kwargs(runner, runner_kwargs)
            )
            quality_path = outputs.get("quality")
            quality = read_json(quality_path) if quality_path and quality_path.exists() else {}
            jobs.mark_completed(job_id, outputs=outputs, quality=quality)
        except Exception as exc:  # pragma: no cover - exercised manually with real APIs
            jobs.mark_failed(job_id, format_job_error(exc))

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
            **runtime.readiness(probe_provider=probe_provider, provider_probe=provider_probe),
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
        parser_profiles = routing_parser_profiles_config()
        return {
            "default_scenario_id": runtime.default_scenario_id,
            "scenarios": scenarios,
            "default_parser_profile_id": parser_profiles.get("default_profile_id", "fast"),
            "parser_profiles": public_parser_profiles(parser_profiles),
        }

    @app.post("/api/generate")
    async def generate(
        background_tasks: BackgroundTasks,
        response: Response,
        request: Request,
        pdf: UploadFile = File(...),
        outline: UploadFile | None = File(None),
        scenario_id: str = Form(""),
        parser_profile_id: str = Form(""),
    ) -> dict[str, Any]:
        set_no_store(response)
        current_user = current_user_or_401(request)
        readiness = runtime.readiness()
        if readiness["status"] != "ready":
            raise HTTPException(status_code=503, detail=readiness)

        try:
            scenario = resolve_scenario(routing_content_config(), scenario_id)
            parser_profile = resolve_parser_profile(
                routing_parser_profiles_config(),
                parser_profile_id,
                is_admin=is_admin_request(request),
                parser_config=runtime.parser_config,
            )
        except ScenarioRoutingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except ParserProfileRoutingError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ParserProfileUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        cleanup_expired_jobs()

        job_id = uuid4().hex[:12]
        job_dir = jobs_root / job_id
        input_dir = job_dir / "input"
        pdf_name = safe_upload_name(pdf.filename or "", "courseware.pdf")
        if Path(pdf_name).suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Uploaded file must be a PDF")
        pdf_path = input_dir / pdf_name
        await save_pdf_upload(pdf, pdf_path, runtime.max_pdf_bytes)

        outline_path = None
        if outline is not None and outline.filename:
            outline_name = safe_upload_name(outline.filename, "outline.md")
            outline_path = input_dir / outline_name
            await save_upload(outline, outline_path)

        content_paths = selected_content_paths(scenario)
        jobs.create(
            job_id=job_id,
            pdf_path=pdf_path,
            outline_path=outline_path,
            output_dir=job_dir / "output",
            metadata={
                "owner_user_id": current_user.id,
                "scenario": scenario.trace_metadata(),
                "parser_profile": parser_profile.trace_metadata(),
                "content_paths": content_paths,
            },
        )
        background_tasks.add_task(run_job, job_id)
        return {
            "job_id": job_id,
            "status": "queued",
            "status_url": f"/api/jobs/{job_id}",
        }

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_no_store(response)
        job = job_or_404(job_id, current_user_or_401(request))
        return {
            "job_id": job_id,
            "status": job.status,
            "error": job.error,
            "quality": job.quality,
            "output_url": f"/api/jobs/{job_id}/output",
            "evidence_url": f"/api/jobs/{job_id}/evidence",
            "evidence_links_url": f"/api/jobs/{job_id}/evidence-links",
            "trace_url": f"/api/jobs/{job_id}/trace",
            "pdf_url": f"/api/jobs/{job_id}/pdf",
            "pdf_info_url": f"/api/jobs/{job_id}/pdf-info",
            "pdf_page_url_template": f"/api/jobs/{job_id}/pdf-page/{{page}}.png",
        }

    @app.get("/api/jobs/{job_id}/output")
    def job_output(job_id: str, request: Request, response: Response) -> dict[str, str]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, "markdown", "Output is not ready")
        return {"markdown": path.read_text(encoding="utf-8")}

    @app.get("/api/jobs/{job_id}/evidence")
    def job_evidence(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        evidence_path = ready_output_path(job, "evidence", "Evidence is not ready")
        links_path = ready_output_path(job, "evidence_links", "Evidence is not ready")
        return {
            "evidence": read_json(evidence_path),
            "evidence_links": read_json(links_path),
        }

    @app.get("/api/jobs/{job_id}/evidence-links")
    def job_evidence_links(job_id: str, request: Request, response: Response) -> Any:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, "evidence_links", "Evidence links are not ready")
        return read_json(path)

    @app.get("/api/jobs/{job_id}/trace")
    def job_trace(job_id: str, request: Request, response: Response) -> Any:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = ready_output_path(job, "trace", "Retrieval trace is not ready")
        return read_json(path)

    @app.get("/api/jobs/{job_id}/pdf")
    def job_pdf(job_id: str, request: Request) -> FileResponse:
        job = job_or_404(job_id, current_user_or_401(request))
        path = job.pdf_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=path.name,
            headers=private_cache_headers(),
        )

    @app.get("/api/jobs/{job_id}/pdf-info")
    def job_pdf_info(job_id: str, request: Request, response: Response) -> dict[str, Any]:
        set_private_cache(response)
        job = job_or_404(job_id, current_user_or_401(request))
        path = job.pdf_path
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
        return {"page_count": len(pages), "pages": pages}

    @app.get("/api/jobs/{job_id}/pdf-page/{page_no}.png")
    def job_pdf_page_png(job_id: str, page_no: int, request: Request) -> Response:
        job = job_or_404(job_id, current_user_or_401(request))
        path = job.pdf_path
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

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_mvp:app", host="127.0.0.1", port=8765, reload=False)

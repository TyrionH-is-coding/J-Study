from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable
import unicodedata
from uuid import uuid4

import fitz
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from apps.api.jstudy_api.ui import INDEX_HTML

from packages.core.jstudy_core.jobs import JobRecord, JobStore
from packages.core.jstudy_core.pipeline import RagConfig, run_mvp
from packages.core.jstudy_core.settings import RuntimeSettings
from packages.core.jstudy_core.storage import read_json

Runner = Callable[..., dict[str, Path]]


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT = PROJECT_ROOT


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


def create_app(
    base_dir: Path | None = None,
    runner: Runner = run_mvp,
    job_store: JobStore | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    app = FastAPI(title="J Study MVP")
    runtime = settings or RuntimeSettings.from_env(ROOT, jobs_root=base_dir)
    jobs_root = base_dir or runtime.jobs_root
    jobs_root.mkdir(parents=True, exist_ok=True)
    jobs = job_store or JobStore(store_path=jobs_root / "jobs.json")

    def job_or_404(job_id: str) -> JobRecord:
        try:
            return jobs.require(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Job not found")

    def ready_output_path(job: JobRecord, key: str, detail: str) -> Path:
        path = job.outputs.get(key)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail=detail)
        return path

    def run_job(job_id: str) -> None:
        job = jobs.require(job_id)
        jobs.mark_running(job_id)
        try:
            outputs = runner(
                pdf_path=job.pdf_path,
                soul_path=runtime.soul_path,
                mnemonics_path=runtime.mnemonics_path,
                api_key_path=runtime.api_key_path,
                output_dir=job.output_dir,
                chat_model=runtime.chat_model,
                embed_model=runtime.embed_model,
                output_prefix="result",
                rag_config=RagConfig(),
                embedding_cache_path=jobs_root / ".cache" / "embeddings.json",
                outline_path=job.outline_path,
            )
            quality_path = outputs.get("quality")
            quality = read_json(quality_path) if quality_path and quality_path.exists() else {}
            jobs.mark_completed(job_id, outputs=outputs, quality=quality)
        except Exception as exc:  # pragma: no cover - exercised manually with real APIs
            jobs.mark_failed(job_id, format_job_error(exc))

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "jstudy-api"}

    @app.get("/api/readiness")
    def readiness() -> dict[str, Any]:
        return {"service": "jstudy-api", **runtime.readiness()}

    @app.post("/api/generate")
    async def generate(
        background_tasks: BackgroundTasks,
        pdf: UploadFile = File(...),
        outline: UploadFile | None = File(None),
    ) -> dict[str, Any]:
        readiness = runtime.readiness()
        if readiness["status"] != "ready":
            raise HTTPException(status_code=503, detail=readiness)

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

        jobs.create(
            job_id=job_id,
            pdf_path=pdf_path,
            outline_path=outline_path,
            output_dir=job_dir / "output",
        )
        background_tasks.add_task(run_job, job_id)
        return {
            "job_id": job_id,
            "status": "queued",
            "status_url": f"/api/jobs/{job_id}",
        }

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        job = job_or_404(job_id)
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
    def job_output(job_id: str) -> dict[str, str]:
        job = job_or_404(job_id)
        path = ready_output_path(job, "markdown", "Output is not ready")
        return {"markdown": path.read_text(encoding="utf-8")}

    @app.get("/api/jobs/{job_id}/evidence")
    def job_evidence(job_id: str) -> dict[str, Any]:
        job = job_or_404(job_id)
        evidence_path = ready_output_path(job, "evidence", "Evidence is not ready")
        links_path = ready_output_path(job, "evidence_links", "Evidence is not ready")
        return {
            "evidence": read_json(evidence_path),
            "evidence_links": read_json(links_path),
        }

    @app.get("/api/jobs/{job_id}/evidence-links")
    def job_evidence_links(job_id: str) -> Any:
        job = job_or_404(job_id)
        path = ready_output_path(job, "evidence_links", "Evidence links are not ready")
        return read_json(path)

    @app.get("/api/jobs/{job_id}/trace")
    def job_trace(job_id: str) -> Any:
        job = job_or_404(job_id)
        path = ready_output_path(job, "trace", "Retrieval trace is not ready")
        return read_json(path)

    @app.get("/api/jobs/{job_id}/pdf")
    def job_pdf(job_id: str) -> FileResponse:
        job = job_or_404(job_id)
        path = job.pdf_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.get("/api/jobs/{job_id}/pdf-info")
    def job_pdf_info(job_id: str) -> dict[str, Any]:
        job = job_or_404(job_id)
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
    def job_pdf_page_png(job_id: str, page_no: int) -> Response:
        job = job_or_404(job_id)
        path = job.pdf_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")
        with fitz.open(str(path)) as doc:
            if page_no < 1 or page_no > len(doc):
                raise HTTPException(status_code=404, detail="PDF page not found")
            page = doc.load_page(page_no - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            return Response(content=pixmap.tobytes("png"), media_type="image/png")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_mvp:app", host="127.0.0.1", port=8765, reload=False)

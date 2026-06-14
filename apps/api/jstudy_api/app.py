from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import fitz
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

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
    jobs = job_store or JobStore()

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
            jobs.mark_failed(job_id, str(exc))

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.post("/api/generate")
    async def generate(
        background_tasks: BackgroundTasks,
        pdf: UploadFile = File(...),
        outline: UploadFile | None = File(None),
    ) -> dict[str, Any]:
        job_id = uuid4().hex[:12]
        job_dir = jobs_root / job_id
        input_dir = job_dir / "input"
        pdf_name = Path(pdf.filename or "courseware.pdf").name
        pdf_path = input_dir / pdf_name
        await save_upload(pdf, pdf_path)

        outline_path = None
        if outline is not None and outline.filename:
            outline_name = Path(outline.filename).name
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


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>J Study MVP</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17201a;
      --muted: #647067;
      --line: #d8ded8;
      --paper: #fbfbf7;
      --panel: #f0f4ef;
      --accent: #0f766e;
      --accent-strong: #0b4f4a;
      --warn: #9a3412;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }
    .workspace {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr) minmax(360px, 42vw);
      height: 100vh;
      min-height: 100vh;
      overflow: hidden;
    }
    aside, main, .pdf {
      min-width: 0;
      min-height: 0;
      border-right: 1px solid var(--line);
    }
    aside {
      padding: 18px;
      background: var(--panel);
    }
    h1, h2, h3 {
      margin: 0;
      letter-spacing: 0;
      line-height: 1.25;
    }
    h1 { font-size: 22px; }
    h2 { font-size: 18px; margin-top: 24px; }
    h3 { font-size: 15px; margin-top: 18px; }
    label {
      display: block;
      margin-top: 16px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }
    input[type="file"] {
      width: 100%;
      margin-top: 6px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
    }
    button {
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: white;
      padding: 9px 12px;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-strong); }
    button:disabled { opacity: .55; cursor: wait; }
    .run { width: 100%; margin-top: 18px; }
    .status {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      word-break: break-word;
    }
    main {
      padding: 28px;
      overflow-y: auto;
      overflow-x: hidden;
    }
    article {
      max-width: 980px;
      font-size: 15px;
      line-height: 1.75;
    }
    article p { margin: 10px 0; }
    article pre {
      overflow: auto;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      white-space: pre-wrap;
    }
    .evidence-btn {
      display: inline-flex;
      align-items: center;
      margin-left: 6px;
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid #99c7bf;
      background: #e6f4f1;
      color: var(--accent-strong);
      font-size: 12px;
      line-height: 1.5;
    }
    .pdf {
      display: grid;
      grid-template-rows: auto minmax(110px, 18vh) minmax(0, 1fr);
      min-height: 0;
      background: #eef1ec;
      border-right: 0;
    }
    .pdf-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      background: white;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: #edf4ef;
      font-weight: 800;
    }
    .pdf-pages {
      width: 100%;
      height: 100%;
      min-height: 0;
      overflow: auto;
      padding: 16px 14px 26px;
      background: #dfe5df;
      scroll-behavior: smooth;
    }
    .pdf-page {
      margin: 0 auto 18px;
      max-width: 100%;
      border: 1px solid #c6cec7;
      border-radius: 6px;
      background: white;
      box-shadow: 0 4px 14px rgba(23, 32, 26, .12);
      overflow: hidden;
    }
    .pdf-page.active {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, .2), 0 4px 14px rgba(23, 32, 26, .16);
    }
    .pdf-page-label {
      padding: 7px 10px;
      border-bottom: 1px solid var(--line);
      background: #f7faf6;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .pdf-page img {
      display: block;
      width: 100%;
      height: auto;
      background: white;
    }
    .citation-list {
      overflow: auto;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: #f7faf6;
    }
    .citation-item {
      width: 100%;
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 6px 10px;
      margin-bottom: 8px;
      padding: 9px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--ink);
      text-align: left;
      font-weight: 500;
    }
    .citation-item:hover,
    .citation-item.active {
      border-color: #6fb3a8;
      background: #eaf6f2;
    }
    .citation-ref {
      color: var(--accent-strong);
      font-weight: 800;
      white-space: nowrap;
    }
    .citation-meta {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .citation-quote {
      grid-column: 1 / -1;
      color: #2f3b33;
      font-size: 13px;
      line-height: 1.45;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      padding: 18px;
      border-radius: 6px;
    }
    .error { color: var(--warn); font-weight: 700; }
    @media (max-width: 980px) {
      .workspace { grid-template-columns: 1fr; height: auto; overflow: visible; }
      aside, main, .pdf { border-right: 0; border-bottom: 1px solid var(--line); }
      .pdf { min-height: 70vh; }
    }
  </style>
</head>
<body>
  <div class="workspace">
    <aside>
      <h1>J Study MVP</h1>
      <form id="form">
        <label>课件 PDF</label>
        <input name="pdf" type="file" accept="application/pdf" required />
        <label>课程大纲</label>
        <input name="outline" type="file" accept=".md,.txt,.pdf" />
        <button class="run" id="run" type="submit">生成学习资料</button>
      </form>
      <div class="status" id="status">等待上传</div>
    </aside>
    <main>
      <article id="output"><div class="empty">生成后显示学习资料</div></article>
    </main>
    <section class="pdf">
      <div class="pdf-head">
        <strong>课件依据</strong>
        <span id="pdfMeta">未选择</span>
      </div>
      <div class="citation-list" id="evidenceList"><div class="empty">生成后显示 citation 对照</div></div>
      <div class="pdf-pages" id="pdfPages"><div class="empty">生成后显示 PDF 页面预览</div></div>
    </section>
  </div>
  <script>
    const form = document.getElementById("form");
    const run = document.getElementById("run");
    const statusBox = document.getElementById("status");
    const output = document.getElementById("output");
    const pdfMeta = document.getElementById("pdfMeta");
    const evidenceList = document.getElementById("evidenceList");
    const pdfPages = document.getElementById("pdfPages");
    let currentJob = "";
    let evidenceLinks = [];

    function escapeHtml(value) {
      return value.replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }

    function evidenceButtons(ids, seenRefs) {
      return ids.map(id => {
        seenRefs[id] = (seenRefs[id] || 0) + 1;
        return `<button class="evidence-btn" data-ref="${id}" data-occurrence="${seenRefs[id]}" type="button">依据 ${id}</button>`;
      }).join("");
    }

    function renderInlineMarkdown(line) {
      return line
        .split(/(<button class="evidence-btn"[\s\S]*?<\/button>)/g)
        .map(part => {
          if (part.startsWith("<button")) return part;
          return escapeHtml(part)
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");
        })
        .join("");
    }

    function isTableLine(line) {
      return /^\s*\|.+\|\s*$/.test(line);
    }

    function isTableSeparator(line) {
      return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line);
    }

    function splitTableRow(line) {
      return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
    }

    function renderTableBlock(lines) {
      const rows = lines.filter(line => !isTableSeparator(line)).map(splitTableRow);
      if (!rows.length) return "";
      const header = rows[0];
      const body = rows.slice(1);
      return `
        <table>
          <thead><tr>${header.map(cell => `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead>
          <tbody>${body.map(row => `<tr>${row.map(cell => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
        </table>
      `;
    }

    function renderCodeBlock(lines) {
      return `<pre><code>${escapeHtml(lines.join("\n"))}</code></pre>`;
    }

    function renderMarkdown(markdown) {
      const seenRefs = {};
      const withButtons = markdown.replace(/<!--\s*evidence:\s*([^>]+?)\s*-->/gi, (_, raw) => {
        const ids = raw.match(/E\d{3}/g) || [];
        return evidenceButtons(ids, seenRefs);
      });
      const lines = withButtons.split(/\r?\n/);
      const blocks = [];
      for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index];
        if (line.startsWith("```")) {
          const codeLines = [];
          index += 1;
          while (index < lines.length && !lines[index].startsWith("```")) {
            codeLines.push(lines[index]);
            index += 1;
          }
          blocks.push(renderCodeBlock(codeLines));
          continue;
        }
        if (isTableLine(line)) {
          const tableLines = [];
          while (index < lines.length && isTableLine(lines[index])) {
            tableLines.push(lines[index]);
            index += 1;
          }
          index -= 1;
          blocks.push(renderTableBlock(tableLines));
          continue;
        }
        const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
          const level = Math.min(headingMatch[1].length + 1, 6);
          blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
          continue;
        }
        if (line.trim() === "---") {
          blocks.push("<hr>");
          continue;
        }
        if (!line.trim()) continue;
        blocks.push(`<p>${renderInlineMarkdown(line)}</p>`);
      }
      return blocks.join("");
    }

    function findEvidenceLink(ref, occurrence) {
      const wantedOccurrence = Number(occurrence || 1);
      return evidenceLinks.find(item => item.ref_id === ref && Number(item.occurrence || 1) === wantedOccurrence)
        || evidenceLinks.find(item => item.ref_id === ref);
    }

    function renderEvidencePanel(links) {
      if (!links.length) {
        evidenceList.innerHTML = `<div class="empty">没有可显示的 citation 对照</div>`;
        return;
      }
      evidenceList.innerHTML = links.map(link => {
        const target = link.target || {};
        const page = target.page || 1;
        const chunk = target.chunk_id || "";
        const quote = String(target.quote || "").slice(0, 220);
        return `
          <button class="citation-item" data-ref="${link.ref_id}" data-occurrence="${link.occurrence || 1}" type="button">
            <span class="citation-ref">${escapeHtml(link.ref_id)}</span>
            <span class="citation-meta">page ${escapeHtml(String(page))}${chunk ? ` · ${escapeHtml(chunk)}` : ""}</span>
            <span class="citation-quote">${escapeHtml(quote)}</span>
          </button>
        `;
      }).join("");
    }

    function renderPdfPages(pageCount) {
      if (!pageCount) {
        pdfPages.innerHTML = `<div class="empty">无法读取 PDF 页面</div>`;
        return;
      }
      pdfPages.innerHTML = Array.from({ length: pageCount }, (_, index) => {
        const page = index + 1;
        return `
          <figure class="pdf-page" data-page="${page}">
            <figcaption class="pdf-page-label">Page ${page}</figcaption>
            <img loading="lazy" src="/api/jobs/${currentJob}/pdf-page/${page}.png" alt="PDF page ${page}">
          </figure>
        `;
      }).join("");
    }

    function scrollPdfPageIntoView(page) {
      document.querySelectorAll(".pdf-page.active").forEach(item => item.classList.remove("active"));
      const target = pdfPages.querySelector(`.pdf-page[data-page="${page}"]`);
      if (!target) return;
      target.classList.add("active");
      const containerRect = pdfPages.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const top = pdfPages.scrollTop + targetRect.top - containerRect.top - ((pdfPages.clientHeight - targetRect.height) / 2);
      pdfPages.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    }

    function showEvidenceLink(link, options = {}) {
      if (!link || !currentJob) return;
      const page = link.target && link.target.page ? link.target.page : 1;
      pdfMeta.textContent = `${link.ref_id} / page ${page}`;
      scrollPdfPageIntoView(page);
      document.querySelectorAll(".citation-item.active").forEach(item => item.classList.remove("active"));
      const selector = `.citation-item[data-ref="${link.ref_id}"][data-occurrence="${link.occurrence || 1}"]`;
      const active = evidenceList.querySelector(selector);
      if (active) {
        active.classList.add("active");
      }
      if (options.scrollCitationList && active) {
        active.scrollIntoView({ block: "nearest" });
      }
    }

    async function poll(jobId) {
      const res = await fetch(`/api/jobs/${jobId}`);
      const job = await res.json();
      statusBox.textContent = `状态：${job.status}`;
      if (job.status === "completed") {
        const [outRes, evidenceRes, pdfInfoRes] = await Promise.all([
          fetch(job.output_url),
          fetch(job.evidence_url),
          fetch(job.pdf_info_url)
        ]);
        const out = await outRes.json();
        const evidence = await evidenceRes.json();
        const pdfInfo = await pdfInfoRes.json();
        evidenceLinks = evidence.evidence_links || [];
        output.innerHTML = renderMarkdown(out.markdown);
        renderEvidencePanel(evidenceLinks);
        renderPdfPages(pdfInfo.page_count || 0);
        pdfMeta.textContent = job.quality && job.quality.status ? `质量：${job.quality.status}` : "已生成";
        run.disabled = false;
        return;
      }
      if (job.status === "failed") {
        statusBox.innerHTML = `<span class="error">${escapeHtml(job.error || "生成失败")}</span>`;
        run.disabled = false;
        return;
      }
      setTimeout(() => poll(jobId), 1200);
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      run.disabled = true;
      statusBox.textContent = "上传中";
      output.innerHTML = `<div class="empty">生成中</div>`;
      evidenceList.innerHTML = `<div class="empty">等待 citation</div>`;
      pdfPages.innerHTML = `<div class="empty">等待 PDF 预览</div>`;
      const res = await fetch("/api/generate", { method: "POST", body: new FormData(form) });
      const data = await res.json();
      currentJob = data.job_id;
      poll(currentJob);
    });

    output.addEventListener("click", event => {
      const button = event.target.closest(".evidence-btn");
      if (!button || !currentJob) return;
      const ref = button.dataset.ref;
      const link = findEvidenceLink(ref, button.dataset.occurrence);
      showEvidenceLink(link, { scrollCitationList: false });
    });

    evidenceList.addEventListener("click", event => {
      const button = event.target.closest(".citation-item");
      if (!button || !currentJob) return;
      const link = findEvidenceLink(button.dataset.ref, button.dataset.occurrence);
      showEvidenceLink(link, { scrollCitationList: true });
    });
  </script>
</body>
</html>
"""


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_mvp:app", host="127.0.0.1", port=8765, reload=False)

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

import uvicorn

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from apps.api.jstudy_api.app import create_app  # noqa: E402
from packages.core.jstudy_core.auth_db import (  # noqa: E402
    create_application_tables,
    create_auth_engine,
)
from packages.core.jstudy_core.job_system.repository import JobRepository  # noqa: E402
from packages.core.jstudy_core.job_system.states import JobState  # noqa: E402
from packages.core.jstudy_core.job_system.worker import (  # noqa: E402
    JobWorker,
    PermanentJobError,
)
from packages.core.jstudy_core.settings import RuntimeSettings  # noqa: E402


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def deterministic_runner(**kwargs) -> dict[str, Path]:
    pdf_paths = kwargs.get("pdf_paths") or [kwargs["pdf_path"]]
    source_files = kwargs.get("source_files") or []
    if any(
        "fail" in source["file_name"].lower()
        for source in source_files
    ):
        raise PermanentJobError(
            "deterministic_e2e_failure",
            "deterministic E2E generation failure",
        )

    progress_callback = kwargs["progress_callback"]
    for state in (
        JobState.PARSING,
        JobState.RETRIEVING,
        JobState.GENERATING,
        JobState.PACKAGING,
    ):
        progress_callback(state)

    time.sleep(0.25)
    output_dir = kwargs["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = kwargs["output_prefix"]
    target_source = source_files[-1] if source_files else {"source_id": "S001", "file_name": pdf_paths[-1].name}
    target_source_id = target_source["source_id"]
    target_file = target_source["file_name"]
    markdown = (
        "## Unit One\n\n"
        "The first unit is linked to its course source. <!-- evidence: E001 -->\n\n"
        "## Unit Two\n\n"
        "Evidence for this outline section is currently weak.\n"
    )
    paths = {
        "markdown": output_dir / f"{prefix}-output.md",
        "evidence": output_dir / f"{prefix}-evidence.json",
        "evidence_links": output_dir / f"{prefix}-evidence_links.json",
        "quality": output_dir / f"{prefix}-quality.json",
        "trace": output_dir / f"{prefix}-retrieval_trace.json",
        "package": output_dir / f"{prefix}-package.json",
    }
    paths["markdown"].write_text(markdown, encoding="utf-8")
    evidence = [{
        "id": "E001",
        "source_id": target_source_id,
        "source_file": target_file,
        "page": 2,
        "chunk_id": f"{target_source_id}-C002",
        "score": 0.91,
        "excerpt": "The first unit is linked to its course source.",
    }]
    write_json(paths["evidence"], evidence)
    write_json(paths["evidence_links"], [{
        "ref_id": "E001",
        "occurrence": 1,
        "comment_index": 1,
        "target": {
            "source_id": target_source_id,
            "source_file": target_file,
            "page": 2,
            "chunk_id": f"{target_source_id}-C002",
            "quote": "The first unit is linked to its course source.",
        },
    }])
    write_json(paths["quality"], {"status": "pass"})
    write_json(paths["trace"], {"service_mode": "course_outline", "source_files": source_files})
    write_json(paths["package"], {
        "type": "material_package",
        "service_mode": "course_outline",
        "generation_mode": "",
        "source_files": source_files,
        "sections": [
            {
                "id": "section-001",
                "title": "Unit One",
                "order": 1,
                "status": "generated",
                "quality": {"evidence_count": 1},
                "source_files": [target_source_id],
                "evidence_ids": ["E001"],
                "artifact_filenames": {key: path.name for key, path in paths.items()},
            },
            {
                "id": "section-002",
                "title": "Unit Two",
                "order": 2,
                "status": "weak_evidence",
                "quality": {"evidence_count": 0},
                "source_files": [],
                "evidence_ids": [],
                "artifact_filenames": {key: path.name for key, path in paths.items()},
            },
        ],
    })
    return paths


def build_settings(root: Path) -> RuntimeSettings:
    soul_path = root / "config" / "soul.md"
    mnemonics_path = root / "config" / "mnemonics.md"
    api_key_path = root / "secrets" / "api-key.txt"
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    api_key_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text("e2e soul", encoding="utf-8")
    mnemonics_path.write_text("e2e mnemonics", encoding="utf-8")
    api_key_path.write_text("e2e-key", encoding="utf-8")
    return RuntimeSettings(
        project_root=root,
        jobs_root=root / "jobs",
        soul_path=soul_path,
        mnemonics_path=mnemonics_path,
        api_key_path=api_key_path,
        chat_model="e2e-chat",
        embed_model="e2e-embed",
        database_url=f"sqlite:///{(root / 'jstudy.db').as_posix()}",
        session_secret="e2e-session-secret",
        invite_required=False,
        worker_poll_seconds=1,
        worker_lease_seconds=30,
    )


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="jstudy-e2e-") as temporary:
        root = Path(temporary)
        settings = build_settings(root)
        engine = create_auth_engine(settings.database_url)
        create_application_tables(engine)
        repository = JobRepository(engine)
        app = create_app(settings=settings, job_repository=repository)
        worker = JobWorker(
            repository,
            settings,
            worker_id="e2e-worker",
            single_runner=deterministic_runner,
            outline_runner=deterministic_runner,
        )
        stop_event = threading.Event()
        worker_thread = threading.Thread(
            target=worker.run_forever,
            args=(stop_event,),
            name="jstudy-e2e-worker",
            daemon=True,
        )
        worker_thread.start()
        try:
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=int(os.environ.get("JSTUDY_E2E_API_PORT", "8130")),
                log_level="warning",
            )
        finally:
            stop_event.set()
            worker_thread.join(timeout=5)
            engine.dispose()

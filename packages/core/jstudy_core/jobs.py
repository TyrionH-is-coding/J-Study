from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class JobRecord:
    job_id: str
    status: str
    pdf_path: Path
    output_dir: Path
    outline_path: Path | None = None
    outputs: dict[str, Path] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create(
        self,
        job_id: str,
        pdf_path: Path,
        output_dir: Path,
        outline_path: Path | None = None,
    ) -> JobRecord:
        record = JobRecord(
            job_id=job_id,
            status="queued",
            pdf_path=pdf_path,
            outline_path=outline_path,
            output_dir=output_dir,
        )
        self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def require(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        return record

    def mark_running(self, job_id: str) -> None:
        self.require(job_id).status = "running"

    def mark_completed(
        self,
        job_id: str,
        outputs: dict[str, Path],
        quality: dict[str, Any],
    ) -> None:
        record = self.require(job_id)
        record.status = "completed"
        record.outputs = outputs
        record.quality = quality
        record.error = ""

    def mark_failed(self, job_id: str, error: str) -> None:
        record = self.require(job_id)
        record.status = "failed"
        record.error = error

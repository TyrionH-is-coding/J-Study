from __future__ import annotations

import json
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "pdf_path": str(self.pdf_path),
            "output_dir": str(self.output_dir),
            "outline_path": str(self.outline_path) if self.outline_path else None,
            "outputs": {key: str(path) for key, path in self.outputs.items()},
            "quality": self.quality,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRecord":
        outline_path = payload.get("outline_path")
        return cls(
            job_id=payload["job_id"],
            status=payload["status"],
            pdf_path=Path(payload["pdf_path"]),
            output_dir=Path(payload["output_dir"]),
            outline_path=Path(outline_path) if outline_path else None,
            outputs={key: Path(path) for key, path in payload.get("outputs", {}).items()},
            quality=payload.get("quality", {}),
            error=payload.get("error", ""),
        )


class JobStore:
    def __init__(self, store_path: Path | None = None) -> None:
        self._store_path = store_path
        self._jobs: dict[str, JobRecord] = {}
        self._load()

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
        self._save()
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
        self._save()

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
        self._save()

    def mark_failed(self, job_id: str, error: str) -> None:
        record = self.require(job_id)
        record.status = "failed"
        record.error = error
        self._save()

    def _load(self) -> None:
        if self._store_path is None or not self._store_path.exists():
            return

        payload = json.loads(self._store_path.read_text(encoding="utf-8"))
        changed = False
        for raw in payload.get("jobs", []):
            record = JobRecord.from_dict(raw)
            if record.status in {"queued", "running"}:
                record.status = "failed"
                record.error = "Job interrupted by server restart"
                changed = True
            self._jobs[record.job_id] = record
        if changed:
            self._save()

    def _save(self) -> None:
        if self._store_path is None:
            return

        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "jobs": [job.to_dict() for job in self._jobs.values()]}
        tmp_path = self._store_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self._store_path)

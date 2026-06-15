from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_datetime(value: str) -> datetime | None:
    try:
        return normalized_datetime(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None


@dataclass
class JobRecord:
    job_id: str
    status: str
    pdf_path: Path
    output_dir: Path
    outline_path: Path | None = None
    outputs: dict[str, Path] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "pdf_path": str(self.pdf_path),
            "output_dir": str(self.output_dir),
            "outline_path": str(self.outline_path) if self.outline_path else None,
            "outputs": {key: str(path) for key, path in self.outputs.items()},
            "quality": self.quality,
            "metadata": self.metadata,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRecord":
        outline_path = payload.get("outline_path")
        now = utc_now_iso()
        created_at = str(payload.get("created_at") or now)
        return cls(
            job_id=payload["job_id"],
            status=payload["status"],
            pdf_path=Path(payload["pdf_path"]),
            output_dir=Path(payload["output_dir"]),
            outline_path=Path(outline_path) if outline_path else None,
            outputs={key: Path(path) for key, path in payload.get("outputs", {}).items()},
            quality=payload.get("quality", {}),
            metadata=payload.get("metadata", {}),
            error=payload.get("error", ""),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
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
        metadata: dict[str, Any] | None = None,
    ) -> JobRecord:
        record = JobRecord(
            job_id=job_id,
            status="queued",
            pdf_path=pdf_path,
            outline_path=outline_path,
            output_dir=output_dir,
            metadata=metadata or {},
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
        record = self.require(job_id)
        record.status = "running"
        record.updated_at = utc_now_iso()
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
        record.updated_at = utc_now_iso()
        self._save()

    def mark_failed(self, job_id: str, error: str) -> None:
        record = self.require(job_id)
        record.status = "failed"
        record.error = error
        record.updated_at = utc_now_iso()
        self._save()

    def cleanup_finished_older_than(self, cutoff: datetime, delete_files: bool = False) -> list[str]:
        normalized_cutoff = normalized_datetime(cutoff)
        pruned: list[str] = []

        for job_id, record in list(self._jobs.items()):
            if record.status not in {"completed", "failed"}:
                continue
            updated_at = parse_datetime(record.updated_at) or parse_datetime(record.created_at)
            if updated_at is None or updated_at >= normalized_cutoff:
                continue
            if delete_files:
                self._delete_job_files(record)
            self._jobs.pop(job_id, None)
            pruned.append(job_id)

        if pruned:
            self._save()
        return pruned

    def _delete_job_files(self, record: JobRecord) -> None:
        if self._store_path is None:
            return

        jobs_root = self._store_path.parent.resolve()
        job_dir = record.output_dir.parent.resolve()
        if job_dir.parent != jobs_root or job_dir.name != record.job_id:
            return
        shutil.rmtree(job_dir, ignore_errors=True)

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
                record.updated_at = utc_now_iso()
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

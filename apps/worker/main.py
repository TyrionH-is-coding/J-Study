from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packages.core.jstudy_core.auth_db import (
    create_application_tables,
    create_auth_engine,
)
from packages.core.jstudy_core.job_system.repository import JobRepository
from packages.core.jstudy_core.job_system.worker import JobWorker
from packages.core.jstudy_core.pipeline import PROJECT_ROOT
from packages.core.jstudy_core.settings import RuntimeSettings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the J-Study durable job worker.",
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args(argv)


def build_worker(project_root: Path) -> JobWorker:
    settings = RuntimeSettings.from_env(project_root)
    engine = create_auth_engine(settings.database_url)
    create_application_tables(engine)
    return JobWorker(
        JobRepository(engine),
        settings,
        settings_provider=lambda: RuntimeSettings.from_env(
            project_root,
            jobs_root=settings.jobs_root,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    worker = build_worker(args.project_root)
    if args.once:
        worker.run_once()
        return 0
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

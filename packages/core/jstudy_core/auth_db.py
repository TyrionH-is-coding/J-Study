from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from packages.core.jstudy_core import auth_models  # noqa: F401
from packages.core.jstudy_core.job_system import models as job_models  # noqa: F401


def create_auth_engine(database_url: str) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False
        engine = create_engine(database_url, connect_args=connect_args, poolclass=NullPool)

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(database_url, connect_args=connect_args)


def create_application_tables(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def create_auth_tables(engine: Engine) -> None:
    create_application_tables(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

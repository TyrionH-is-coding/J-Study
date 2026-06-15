from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from packages.core.jstudy_core import auth_models  # noqa: F401


def create_auth_engine(database_url: str) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False
        return create_engine(database_url, connect_args=connect_args, poolclass=NullPool)
    return create_engine(database_url, connect_args=connect_args)


def create_auth_tables(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

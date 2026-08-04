from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    email_verified: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_login_at: datetime | None = None


class InviteCode(SQLModel, table=True):
    __tablename__ = "invite_codes"

    id: str = Field(default_factory=new_id, primary_key=True)
    code: str = Field(index=True, unique=True)
    label: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    disabled_at: datetime | None = None


class InviteCodeUse(SQLModel, table=True):
    __tablename__ = "invite_code_uses"

    id: str = Field(default_factory=new_id, primary_key=True)
    invite_code_id: str = Field(index=True)
    user_id: str = Field(index=True)
    email: str = Field(index=True)
    used_at: datetime = Field(default_factory=utc_now)


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

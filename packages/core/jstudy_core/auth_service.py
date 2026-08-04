from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets

from pwdlib import PasswordHash
from sqlalchemy.engine import Engine
from sqlmodel import select

from packages.core.jstudy_core.auth_db import session_scope
from packages.core.jstudy_core.auth_models import InviteCode, InviteCodeUse, User, UserSession


class AuthServiceError(ValueError):
    pass


class DuplicateEmailError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


class InvalidInviteCodeError(AuthServiceError):
    pass


class InviteCodeExistsError(AuthServiceError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_invite_code(code: str) -> str:
    return code.strip()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, engine: Engine, invite_required: bool = True):
        self.engine = engine
        self.invite_required = invite_required
        self.password_hash = PasswordHash.recommended()

    def create_invite_code(self, code: str, label: str = "") -> InviteCode:
        normalized = normalize_invite_code(code)
        if not normalized:
            raise InvalidInviteCodeError("Invite code is required")
        with session_scope(self.engine) as session:
            existing = session.exec(select(InviteCode).where(InviteCode.code == normalized)).first()
            if existing is not None:
                raise InviteCodeExistsError("Invite code already exists")
            invite = InviteCode(code=normalized, label=label.strip())
            session.add(invite)
            return invite

    def list_invite_codes(self) -> list[InviteCode]:
        with session_scope(self.engine) as session:
            return list(session.exec(select(InviteCode).order_by(InviteCode.created_at)).all())

    def set_invite_code_enabled(self, invite_id: str, enabled: bool) -> InviteCode:
        with session_scope(self.engine) as session:
            invite = session.get(InviteCode, invite_id)
            if invite is None:
                raise InvalidInviteCodeError("Invite code not found")
            invite.enabled = enabled
            invite.updated_at = now_utc()
            invite.disabled_at = None if enabled else now_utc()
            session.add(invite)
            return invite

    def list_invite_uses(self, invite_id: str) -> list[InviteCodeUse]:
        with session_scope(self.engine) as session:
            return list(
                session.exec(
                    select(InviteCodeUse)
                    .where(InviteCodeUse.invite_code_id == invite_id)
                    .order_by(InviteCodeUse.used_at)
                ).all()
            )

    def register(self, email: str, password: str, invite_code: str) -> User:
        normalized_email = normalize_email(email)
        if not normalized_email or "@" not in normalized_email:
            raise AuthServiceError("Valid email is required")
        if len(password) < 8:
            raise AuthServiceError("Password must be at least 8 characters")
        code = normalize_invite_code(invite_code)
        if self.invite_required and not code:
            raise InvalidInviteCodeError("Invite code is required")

        with session_scope(self.engine) as session:
            existing_user = session.exec(select(User).where(User.email == normalized_email)).first()
            if existing_user is not None:
                raise DuplicateEmailError("Email is already registered")
            invite = None
            if self.invite_required:
                invite = session.exec(select(InviteCode).where(InviteCode.code == code)).first()
                if invite is None or not invite.enabled:
                    raise InvalidInviteCodeError("Invite code is invalid")

            user = User(
                email=normalized_email,
                password_hash=self.password_hash.hash(password),
                email_verified=False,
            )
            session.add(user)
            session.flush()
            if invite is not None:
                session.add(InviteCodeUse(invite_code_id=invite.id, user_id=user.id, email=user.email))
            return user

    def login(self, email: str, password: str) -> tuple[User, str]:
        normalized_email = normalize_email(email)
        with session_scope(self.engine) as session:
            user = session.exec(select(User).where(User.email == normalized_email)).first()
            if user is None or not user.is_active:
                raise InvalidCredentialsError("Invalid email or password")
            if not self.password_hash.verify(password, user.password_hash):
                raise InvalidCredentialsError("Invalid email or password")
            user.last_login_at = now_utc()
            user.updated_at = now_utc()
            session.add(user)
            raw_token = self._create_session(session, user.id)
            return user, raw_token

    def create_session(self, user_id: str) -> str:
        with session_scope(self.engine) as session:
            if session.get(User, user_id) is None:
                raise InvalidCredentialsError("User not found")
            return self._create_session(session, user_id)

    def get_user_by_token(self, token: str) -> User | None:
        hashed = token_hash(token)
        with session_scope(self.engine) as session:
            user_session = session.exec(select(UserSession).where(UserSession.token_hash == hashed)).first()
            if user_session is None:
                return None
            user = session.get(User, user_session.user_id)
            if user is None or not user.is_active:
                return None
            return user

    def get_user(self, user_id: str) -> User | None:
        with session_scope(self.engine) as session:
            return session.get(User, user_id)

    def logout(self, token: str) -> None:
        hashed = token_hash(token)
        with session_scope(self.engine) as session:
            user_session = session.exec(select(UserSession).where(UserSession.token_hash == hashed)).first()
            if user_session is not None:
                session.delete(user_session)

    def _create_session(self, session, user_id: str) -> str:
        raw_token = secrets.token_urlsafe(32)
        session.add(UserSession(user_id=user_id, token_hash=token_hash(raw_token)))
        return raw_token

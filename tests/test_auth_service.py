import tempfile
import unittest
from pathlib import Path

from sqlmodel import Session, select

from packages.core.jstudy_core.auth_db import create_auth_engine, create_auth_tables
from packages.core.jstudy_core.auth_models import InviteCodeUse, User, UserSession
from packages.core.jstudy_core.auth_service import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
)


class AuthServiceTest(unittest.TestCase):
    def make_service(self) -> tuple[AuthService, object]:
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "auth.db"
        engine = create_auth_engine(f"sqlite:///{db_path.as_posix()}")
        self.engine = engine
        create_auth_tables(engine)
        return AuthService(engine), engine

    def tearDown(self):
        engine = getattr(self, "engine", None)
        if engine is not None:
            engine.dispose()
        tmp = getattr(self, "tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_shared_invite_code_registers_multiple_users(self):
        service, _engine = self.make_service()
        invite = service.create_invite_code("MED-PILOT", label="Medicine pilot")

        first = service.register("First@Example.com", "password123", "MED-PILOT")
        second = service.register("second@example.com", "password456", "MED-PILOT")
        uses = service.list_invite_uses(invite.id)

        self.assertEqual(first.email, "first@example.com")
        self.assertEqual(second.email, "second@example.com")
        self.assertFalse(first.email_verified)
        self.assertEqual([item.email for item in uses], ["first@example.com", "second@example.com"])

    def test_disabled_invite_code_is_rejected(self):
        service, _engine = self.make_service()
        invite = service.create_invite_code("MED-PILOT")
        service.set_invite_code_enabled(invite.id, False)

        with self.assertRaises(InvalidInviteCodeError):
            service.register("student@example.com", "password123", "MED-PILOT")

    def test_invite_can_be_disabled_for_small_pilot(self):
        _service, engine = self.make_service()
        service = AuthService(engine, invite_required=False)

        user = service.register("student@example.com", "password123", "")
        with Session(engine) as session:
            invite_uses = session.exec(select(InviteCodeUse)).all()

        self.assertEqual(user.email, "student@example.com")
        self.assertEqual(invite_uses, [])

    def test_duplicate_email_is_rejected(self):
        service, _engine = self.make_service()
        service.create_invite_code("MED-PILOT")
        service.register("student@example.com", "password123", "MED-PILOT")

        with self.assertRaises(DuplicateEmailError):
            service.register("STUDENT@example.com", "password456", "MED-PILOT")

    def test_password_is_hashed_and_login_creates_hashed_session(self):
        service, engine = self.make_service()
        service.create_invite_code("MED-PILOT")
        user = service.register("student@example.com", "password123", "MED-PILOT")

        logged_in, token = service.login("student@example.com", "password123")
        with Session(engine) as session:
            stored_user = session.exec(select(User).where(User.id == user.id)).one()
            stored_session = session.exec(select(UserSession).where(UserSession.user_id == user.id)).one()

        self.assertEqual(logged_in.id, user.id)
        self.assertNotEqual(stored_user.password_hash, "password123")
        self.assertNotIn("password123", stored_user.password_hash)
        self.assertNotEqual(stored_session.token_hash, token)
        self.assertEqual(service.get_user_by_token(token).id, user.id)

    def test_invalid_login_is_rejected(self):
        service, _engine = self.make_service()
        service.create_invite_code("MED-PILOT")
        service.register("student@example.com", "password123", "MED-PILOT")

        with self.assertRaises(InvalidCredentialsError):
            service.login("student@example.com", "wrong-password")
        with self.assertRaises(InvalidCredentialsError):
            service.login("missing@example.com", "password123")

    def test_logout_deletes_session(self):
        service, _engine = self.make_service()
        service.create_invite_code("MED-PILOT")
        user = service.register("student@example.com", "password123", "MED-PILOT")
        _logged_in, token = service.login("student@example.com", "password123")

        service.logout(token)

        self.assertIsNone(service.get_user_by_token(token))
        self.assertEqual(service.get_user(user.id).email, "student@example.com")


if __name__ == "__main__":
    unittest.main()

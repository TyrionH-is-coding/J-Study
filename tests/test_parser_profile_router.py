import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.core.jstudy_core.parser_profile_router import (  # noqa: E402
    ParserProfileRoutingError,
    ParserProfileUnavailable,
    public_parser_profiles,
    resolve_parser_profile,
)


class ParserProfileRouterTest(unittest.TestCase):
    def config(self):
        return {
            "default_profile_id": "fast",
            "profiles": [
                {
                    "id": "fast",
                    "display_name": "Fast parsing",
                    "backend": "pymupdf",
                    "enabled": True,
                    "visible_to_users": True,
                    "requires_admin": False,
                    "tier": "free",
                    "estimated_wait": "Short",
                },
                {
                    "id": "quality",
                    "display_name": "Quality parsing",
                    "backend": "mineru",
                    "enabled": True,
                    "visible_to_users": False,
                    "requires_admin": True,
                    "tier": "internal",
                    "estimated_wait": "Longer",
                },
            ],
        }

    def test_uses_default_fast_profile(self):
        resolved = resolve_parser_profile(self.config(), requested_profile_id="", is_admin=False)

        self.assertEqual(resolved.profile_id, "fast")
        self.assertEqual(resolved.backend, "pymupdf")

    def test_public_profiles_hide_admin_quality(self):
        profiles = public_parser_profiles(self.config())

        self.assertEqual([item["id"] for item in profiles], ["fast"])

    def test_rejects_hidden_quality_for_normal_user(self):
        with self.assertRaises(ParserProfileRoutingError):
            resolve_parser_profile(self.config(), requested_profile_id="quality", is_admin=False)

    def test_allows_hidden_quality_for_admin(self):
        resolved = resolve_parser_profile(self.config(), requested_profile_id="quality", is_admin=True)

        self.assertEqual(resolved.backend, "mineru")
        self.assertTrue(resolved.requires_admin)

    def test_rejects_mineru_when_not_configured(self):
        with self.assertRaises(ParserProfileUnavailable):
            resolve_parser_profile(
                self.config(),
                requested_profile_id="quality",
                is_admin=True,
                parser_config={"mineru": {"api_token": "", "local_cli_path": ""}},
            )


if __name__ == "__main__":
    unittest.main()

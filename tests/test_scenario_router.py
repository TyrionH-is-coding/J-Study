import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.core.jstudy_core.scenario_router import (  # noqa: E402
    ScenarioRoutingError,
    resolve_scenario,
)


class ScenarioRouterTest(unittest.TestCase):
    def test_uses_default_when_user_does_not_choose(self):
        config = {
            "default_scenario_id": "medicine-default",
            "packs": [{"id": "medicine-default", "enabled": True}],
            "scenarios": [
                {"id": "medicine-default", "enabled": True, "content_pack_id": "medicine-default"}
            ],
        }

        resolved = resolve_scenario(config, requested_scenario_id="")

        self.assertEqual(resolved.scenario_id, "medicine-default")
        self.assertEqual(resolved.content_pack["id"], "medicine-default")

    def test_user_choice_overrides_default(self):
        config = {
            "default_scenario_id": "medicine-default",
            "packs": [
                {"id": "medicine-default", "enabled": True},
                {"id": "general-default", "enabled": True},
            ],
            "scenarios": [
                {"id": "medicine-default", "enabled": True, "content_pack_id": "medicine-default"},
                {"id": "general-default", "enabled": True, "content_pack_id": "general-default"},
            ],
        }

        resolved = resolve_scenario(config, requested_scenario_id="general-default")

        self.assertEqual(resolved.scenario_id, "general-default")
        self.assertEqual(resolved.content_pack["id"], "general-default")

    def test_resolves_prompt_profile_to_soul_profile(self):
        config = {
            "default_scenario_id": "medicine-default",
            "packs": [
                {"id": "medicine-default", "enabled": True},
                {"id": "engineering-default", "enabled": True},
            ],
            "soul_profiles": [
                {"id": "medicine-default", "soul_path": "soul.md"},
                {"id": "engineering-blank", "soul_path": "souls/engineering.md"},
            ],
            "scenarios": [
                {
                    "id": "medicine-default",
                    "enabled": True,
                    "content_pack_id": "medicine-default",
                    "prompt_profile": "medicine-default",
                },
                {
                    "id": "engineering-default",
                    "enabled": True,
                    "content_pack_id": "engineering-default",
                    "prompt_profile": "engineering-blank",
                },
            ],
        }

        resolved = resolve_scenario(config, requested_scenario_id="engineering-default")

        self.assertEqual(resolved.soul_profile["id"], "engineering-blank")
        self.assertEqual(resolved.soul_profile["soul_path"], "souls/engineering.md")

    def test_rejects_disabled_scenario(self):
        config = {
            "default_scenario_id": "medicine-default",
            "packs": [{"id": "medicine-default", "enabled": True}],
            "scenarios": [
                {"id": "medicine-default", "enabled": False, "content_pack_id": "medicine-default"}
            ],
        }

        with self.assertRaises(ScenarioRoutingError):
            resolve_scenario(config, requested_scenario_id="medicine-default")


if __name__ == "__main__":
    unittest.main()

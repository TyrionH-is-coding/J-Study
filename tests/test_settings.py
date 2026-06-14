import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from packages.core.jstudy_core.settings import RuntimeSettings


class SettingsTest(unittest.TestCase):
    def test_runtime_settings_loads_deployment_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "JSTUDY_JOBS_DIR": str(root / "data" / "jobs"),
                "JSTUDY_SOUL_PATH": str(root / "config" / "soul.md"),
                "JSTUDY_MNEMONICS_PATH": str(root / "config" / "mnemonics.md"),
                "SILICONFLOW_API_KEY_FILE": str(root / "secrets" / "api-key.txt"),
                "SILICONFLOW_CHAT_MODEL": "chat-model",
                "SILICONFLOW_EMBED_MODEL": "embed-model",
            }

            with patch.dict(os.environ, env, clear=False):
                settings = RuntimeSettings.from_env(root)

        self.assertEqual(settings.jobs_root, Path(env["JSTUDY_JOBS_DIR"]))
        self.assertEqual(settings.soul_path, Path(env["JSTUDY_SOUL_PATH"]))
        self.assertEqual(settings.mnemonics_path, Path(env["JSTUDY_MNEMONICS_PATH"]))
        self.assertEqual(settings.api_key_path, Path(env["SILICONFLOW_API_KEY_FILE"]))
        self.assertEqual(settings.chat_model, "chat-model")
        self.assertEqual(settings.embed_model, "embed-model")

    def test_runtime_settings_keep_mvp_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {}, clear=True):
                settings = RuntimeSettings.from_env(root)

        self.assertEqual(settings.jobs_root, root / "web_jobs")
        self.assertEqual(settings.soul_path, root / "soul.md")
        self.assertEqual(settings.mnemonics_path, root / "mnemonics.md")
        self.assertEqual(settings.api_key_path, root / "siliconflow api key.txt")


if __name__ == "__main__":
    unittest.main()

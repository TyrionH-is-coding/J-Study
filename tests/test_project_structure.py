import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ProjectStructureTest(unittest.TestCase):
    def test_backend_imports_have_canonical_and_legacy_paths(self):
        from apps.api.jstudy_api.app import INDEX_HTML, app, create_app
        from packages.core.jstudy_core.pipeline import RagConfig, run_mvp
        from mvp_runner import run_mvp as legacy_run_mvp
        from web_mvp import create_app as legacy_create_app

        self.assertTrue(INDEX_HTML.startswith("<!doctype html>"))
        self.assertEqual(app.title, "J Study MVP")
        self.assertIs(legacy_create_app, create_app)
        self.assertIs(legacy_run_mvp, run_mvp)
        self.assertEqual(RagConfig().per_query_limit, 2)


if __name__ == "__main__":
    unittest.main()

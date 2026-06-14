import tempfile
import unittest
from pathlib import Path

from packages.core.jstudy_core.storage import build_output_paths, read_json, write_json


class StorageTest(unittest.TestCase):
    def test_build_output_paths_uses_existing_mvp_file_contract(self):
        paths = build_output_paths(Path("output"), "result")

        self.assertEqual(paths.chunks, Path("output/result-chunks.json"))
        self.assertEqual(paths.trace, Path("output/result-retrieval_trace.json"))
        self.assertEqual(paths.evidence, Path("output/result-evidence.json"))
        self.assertEqual(paths.evidence_links, Path("output/result-evidence_links.json"))
        self.assertEqual(paths.markdown, Path("output/result-output.md"))
        self.assertEqual(paths.quality, Path("output/result-quality.json"))
        self.assertEqual(paths.as_dict()["markdown"], Path("output/result-output.md"))

    def test_json_helpers_write_and_read_utf8_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "quality.json"

            write_json(path, {"status": "pass", "title": "细菌总论"})

            self.assertEqual(read_json(path)["title"], "细菌总论")
            self.assertTrue(path.read_text(encoding="utf-8").endswith("}\n"))


if __name__ == "__main__":
    unittest.main()

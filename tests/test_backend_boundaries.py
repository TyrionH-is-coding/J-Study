import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class BackendBoundariesTest(unittest.TestCase):
    def test_parser_retrieval_and_medicine_modules_are_importable(self):
        from packages.domains.medicine import build_study_queries, parse_mnemonics
        from packages.parsers.pymupdf_parser import extract_pdf_pages
        from packages.retrieval.hybrid import Chunk, RagConfig, chunk_pages

        self.assertTrue(callable(extract_pdf_pages))
        self.assertEqual(RagConfig().chunk_max_chars, 512)
        self.assertEqual(Chunk(id="C001", page=1, text="alpha").id, "C001")
        self.assertGreaterEqual(len(build_study_queries()), 8)
        self.assertEqual(parse_mnemonics("")[0:0], [])

    def test_pipeline_reexports_public_backend_contracts(self):
        from packages.core.jstudy_core import pipeline
        from packages.domains import medicine
        from packages.retrieval import hybrid

        self.assertIs(pipeline.Chunk, hybrid.Chunk)
        self.assertIs(pipeline.RagConfig, hybrid.RagConfig)
        self.assertIs(pipeline.build_study_queries, medicine.build_study_queries)
        self.assertIs(pipeline.extract_evidence_refs, medicine.extract_evidence_refs)


if __name__ == "__main__":
    unittest.main()

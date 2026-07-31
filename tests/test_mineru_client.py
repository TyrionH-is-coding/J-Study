from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import httpx

from packages.core.jstudy_core.documents.models import ParsedDocument, ParsedPage
from packages.core.jstudy_core.documents.mineru_client import (
    MinerUClientConfig,
    MinerUInput,
    MinerUPermanentProviderError,
    MinerUPrecisionClient,
    MinerUProtocolError,
    MinerUProviderError,
    MinerURetryableProviderError,
    MinerUTimeoutError,
)
from packages.parsers.mineru_parser import (
    MinerUAdapterConfigurationError,
    extract_pdf_pages_with_mineru,
)


TOKEN = "test-token-that-must-never-leak"


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += max(seconds, 0.1)


class MinerUClientTest(unittest.TestCase):
    def inputs(self, root: Path, count: int = 2) -> list[MinerUInput]:
        files = []
        for index in range(count):
            path = root / f"lecture-{index + 1}.pdf"
            path.write_bytes(f"pdf-{index + 1}".encode())
            files.append(MinerUInput(source_id=f"S{index + 1:03d}", path=path))
        return files

    def client(
        self,
        handler,
        *,
        clock: FakeClock | None = None,
        **config_overrides,
    ) -> tuple[MinerUPrecisionClient, httpx.Client]:
        config_values = {
            "poll_interval_seconds": 0,
            "deadline_seconds": 10,
            "allowed_download_hosts": ("downloads.example",),
        }
        config_values.update(config_overrides)
        config = MinerUClientConfig(**config_values)
        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        clock = clock or FakeClock()
        return (
            MinerUPrecisionClient(
                token=TOKEN,
                config=config,
                client=http_client,
                sleep=clock.sleep,
                monotonic=clock.monotonic,
            ),
            http_client,
        )

    def success_handler(self, requests: list[httpx.Request]):
        poll_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal poll_count
            requests.append(request)
            self.assertTrue(all(value is not None for value in request.extensions["timeout"].values()))
            if request.method == "POST":
                payload = json.loads(request.content)
                self.assertEqual([item["data_id"] for item in payload["files"]], ["S001", "S002"])
                self.assertEqual(payload["model_version"], "vlm")
                self.assertEqual(request.headers["authorization"], f"Bearer {TOKEN}")
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "trace_id": "submit-trace",
                        "data": {
                            "batch_id": "batch-1",
                            "file_urls": [
                                "https://uploads.example/S001?signature=one",
                                "https://uploads.example/S002?signature=two",
                            ],
                        },
                    },
                )
            if request.method == "PUT":
                self.assertNotIn("authorization", request.headers)
                return httpx.Response(200)
            if request.url.host == "mineru.net":
                poll_count += 1
                state = "running" if poll_count == 1 else "done"
                results = [
                    {
                        "data_id": source_id,
                        "file_name": f"lecture-{index}.pdf",
                        "state": state,
                        **(
                            {"full_zip_url": f"https://downloads.example/{source_id}.zip?secret=query"}
                            if state == "done"
                            else {}
                        ),
                    }
                    for index, source_id in enumerate(("S001", "S002"), start=1)
                ]
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "trace_id": f"poll-trace-{poll_count}",
                        "data": {"batch_id": "batch-1", "extract_result": results},
                    },
                )
            self.assertNotIn("authorization", request.headers)
            return httpx.Response(200, content=f"zip-{request.url.path}".encode())

        return handler

    def test_successful_two_file_flow_is_mocked_and_source_stable(self):
        requests: list[httpx.Request] = []
        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(self.success_handler(requests))
            with http_client:
                artifacts = client.extract(self.inputs(Path(tmp)))

        self.assertEqual([item.source_id for item in artifacts], ["S001", "S002"])
        self.assertEqual([item.provider_trace_id for item in artifacts], ["poll-trace-2"] * 2)
        self.assertEqual([request.method for request in requests], ["POST", "PUT", "PUT", "GET", "GET", "GET", "GET"])

    def test_rejects_file_url_count_mismatch(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": []}},
            )

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUProtocolError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_rejects_provider_error_code(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": -500, "msg": "bad input", "trace_id": "trace"})

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUPermanentProviderError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_http_auth_rejection_is_permanent(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUPermanentProviderError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_failed_extraction_redacts_token_and_signed_query(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if request.method == "POST":
                return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file?secret=upload"]}})
            if request.method == "PUT":
                return httpx.Response(200)
            return httpx.Response(200, json={"code": 0, "trace_id": "poll", "data": {"batch_id": "batch", "extract_result": [{"data_id": "S001", "file_name": "lecture.pdf", "state": "failed", "err_msg": f"token={TOKEN} https://uploads.example/file?secret=result"}]}})

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUPermanentProviderError) as caught:
                client.extract(self.inputs(Path(tmp), count=1))

        message = str(caught.exception)
        self.assertNotIn(TOKEN, message)
        self.assertNotIn("secret=result", message)
        self.assertEqual(calls, 3)

    def test_polling_stops_at_deadline(self):
        clock = FakeClock()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file"]}})
            if request.method == "PUT":
                return httpx.Response(200)
            return httpx.Response(200, json={"code": 0, "trace_id": "poll", "data": {"batch_id": "batch", "extract_result": [{"data_id": "S001", "file_name": "lecture.pdf", "state": "running"}]}})

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler, clock=clock, deadline_seconds=0.2)
            with http_client, self.assertRaises(MinerUTimeoutError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_polling_retries_429_and_5xx_with_bound(self):
        poll_statuses = [429, 503, 200]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file"]}})
            if request.method == "PUT":
                return httpx.Response(200)
            if request.url.host == "mineru.net":
                status = poll_statuses.pop(0)
                if status != 200:
                    return httpx.Response(status)
                return httpx.Response(200, json={"code": 0, "trace_id": "poll", "data": {"batch_id": "batch", "extract_result": [{"data_id": "S001", "file_name": "lecture.pdf", "state": "done", "full_zip_url": "https://downloads.example/file.zip"}]}})
            return httpx.Response(200, content=b"zip")

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client:
                artifacts = client.extract(self.inputs(Path(tmp), count=1))
                zip_content = artifacts[0].zip_path.read_bytes()

        self.assertEqual(zip_content, b"zip")
        self.assertEqual(poll_statuses, [])

    def test_authentication_failure_is_not_retried(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(401)

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUProviderError):
                client.extract(self.inputs(Path(tmp), count=1))

        self.assertEqual(calls, 1)

    def test_rejects_unknown_provider_state(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file"]}})
            if request.method == "PUT":
                return httpx.Response(200)
            return httpx.Response(200, json={"code": 0, "trace_id": "poll", "data": {"batch_id": "batch", "extract_result": [{"data_id": "S001", "file_name": "lecture.pdf", "state": "mystery"}]}})

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUProtocolError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_rejects_non_https_or_unapproved_result_url(self):
        for result_url in ("http://downloads.example/file.zip", "https://evil.example/file.zip"):
            with self.subTest(result_url=result_url):
                def handler(request: httpx.Request) -> httpx.Response:
                    if request.method == "POST":
                        return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file"]}})
                    if request.method == "PUT":
                        return httpx.Response(200)
                    return httpx.Response(200, json={"code": 0, "trace_id": "poll", "data": {"batch_id": "batch", "extract_result": [{"data_id": "S001", "file_name": "lecture.pdf", "state": "done", "full_zip_url": result_url}]}})

                with tempfile.TemporaryDirectory() as tmp:
                    client, http_client = self.client(handler)
                    with http_client, self.assertRaises(MinerUProtocolError):
                        client.extract(self.inputs(Path(tmp), count=1))

    def test_rejects_oversized_result(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file"]}})
            if request.method == "PUT":
                return httpx.Response(200)
            if request.url.host == "mineru.net":
                return httpx.Response(200, json={"code": 0, "trace_id": "poll", "data": {"batch_id": "batch", "extract_result": [{"data_id": "S001", "file_name": "lecture.pdf", "state": "done", "full_zip_url": "https://downloads.example/file.zip"}]}})
            return httpx.Response(200, content=b"too-large")

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler, max_result_bytes=4)
            with http_client, self.assertRaises(MinerUProtocolError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_streams_results_to_private_files_and_enforces_batch_limit(self):
        download_calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "trace_id": "trace",
                        "data": {
                            "batch_id": "batch",
                            "file_urls": [
                                "https://uploads.example/one",
                                "https://uploads.example/two",
                            ],
                        },
                    },
                )
            if request.method == "PUT":
                return httpx.Response(200)
            if request.url.host == "mineru.net":
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "trace_id": "poll",
                        "data": {
                            "batch_id": "batch",
                            "extract_result": [
                                {
                                    "data_id": source_id,
                                    "file_name": f"{source_id}.pdf",
                                    "state": "done",
                                    "full_zip_url": (
                                        f"https://downloads.example/{source_id}.zip"
                                    ),
                                }
                                for source_id in ("S001", "S002")
                            ],
                        },
                    },
                )
            download_calls.append(request.url.path)
            return httpx.Response(200, content=b"1234")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client, http_client = self.client(
                handler,
                max_result_bytes=8,
                max_batch_result_bytes=6,
            )
            with http_client, self.assertRaises(MinerUProtocolError):
                list(
                    client.extract(
                        self.inputs(root),
                        download_root=root / "private-downloads",
                    )
                )
            downloaded = list((root / "private-downloads").glob("*.zip"))

        self.assertEqual(download_calls, ["/S001.zip", "/S002.zip"])
        self.assertEqual(downloaded, [])

    def test_rejects_malformed_download_content_length_without_retry(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "trace_id": "trace",
                        "data": {
                            "batch_id": "batch",
                            "file_urls": ["https://uploads.example/file"],
                        },
                    },
                )
            if request.method == "PUT":
                return httpx.Response(200)
            if request.url.host == "mineru.net":
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "trace_id": "poll",
                        "data": {
                            "batch_id": "batch",
                            "extract_result": [
                                {
                                    "data_id": "S001",
                                    "file_name": "lecture.pdf",
                                    "state": "done",
                                    "full_zip_url": (
                                        "https://downloads.example/file.zip"
                                    ),
                                }
                            ],
                        },
                    },
                )
            return httpx.Response(
                200,
                headers={"content-length": "invalid"},
                content=b"zip",
            )

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUProtocolError):
                client.extract(self.inputs(Path(tmp), count=1))


    def test_rejects_non_mineru_api_origin(self):
        with self.assertRaises(MinerUProtocolError):
            MinerUClientConfig(api_base_url="https://evil.example")

    def test_missing_provider_code_is_protocol_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": {}})

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerUProtocolError):
                client.extract(self.inputs(Path(tmp), count=1))

    def test_submission_transport_error_is_typed_and_safe(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(f"failed with {TOKEN}", request=request)

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler)
            with http_client, self.assertRaises(MinerURetryableProviderError) as caught:
                client.extract(self.inputs(Path(tmp), count=1))

        self.assertNotIn(TOKEN, str(caught.exception))

    def test_polling_retry_exhaustion_is_bounded(self):
        poll_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal poll_calls
            if request.method == "POST":
                return httpx.Response(200, json={"code": 0, "trace_id": "trace", "data": {"batch_id": "batch", "file_urls": ["https://uploads.example/file"]}})
            if request.method == "PUT":
                return httpx.Response(200)
            poll_calls += 1
            return httpx.Response(503)

        with tempfile.TemporaryDirectory() as tmp:
            client, http_client = self.client(handler, max_poll_retries=2)
            with http_client, self.assertRaises(MinerURetryableProviderError):
                client.extract(self.inputs(Path(tmp), count=1))

        self.assertEqual(poll_calls, 3)


class MinerUCompatibilityAdapterTest(unittest.TestCase):
    def document(self) -> ParsedDocument:
        return ParsedDocument(
            contract_version="1",
            source_id="S001",
            source_file="lecture.pdf",
            source_sha256="sha256",
            parser_name="mineru",
            parser_version="v4",
            parser_model="vlm",
            page_count=2,
            pages=[
                ParsedPage(
                    page_number=1, text="Page one", markdown="Page one", blocks=[]
                ),
                ParsedPage(page_number=2, text="  ", markdown="", blocks=[]),
            ],
            warnings=[],
            provider_trace_id="trace",
        )

    def test_requires_explicit_document_parser(self):
        with self.assertRaises(MinerUAdapterConfigurationError):
            extract_pdf_pages_with_mineru(Path("lecture.pdf"))

    def test_adapts_injected_document_parser_to_legacy_pages(self):
        calls = []

        def parser(path: Path, config: dict):
            calls.append((path, config))
            return self.document()

        result = extract_pdf_pages_with_mineru(
            Path("lecture.pdf"),
            {"language": "ch"},
            document_parser=parser,
        )
        self.assertEqual(result, [{"page": 1, "text": "Page one"}])
        self.assertEqual(calls, [(Path("lecture.pdf"), {"language": "ch"})])

    def test_rejects_invalid_document_parser_result(self):
        with self.assertRaises(MinerUAdapterConfigurationError):
            extract_pdf_pages_with_mineru(
                Path("lecture.pdf"),
                document_parser=lambda _path, _config: [],
            )


if __name__ == "__main__":
    unittest.main()

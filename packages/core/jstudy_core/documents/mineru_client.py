from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx


API_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)
UPLOAD_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=120.0, pool=10.0)
DOWNLOAD_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
NONTERMINAL_STATES = {"waiting-file", "pending", "running", "converting"}


class MinerUError(RuntimeError):
    code = "mineru_error"


class MinerUProviderError(MinerUError):
    code = "mineru_provider_error"


class MinerUProtocolError(MinerUError):
    code = "mineru_protocol_error"


class MinerUTimeoutError(MinerUError):
    code = "mineru_timeout"


@dataclass(frozen=True)
class MinerUInput:
    source_id: str
    path: Path


@dataclass(frozen=True)
class MinerUProviderTrace:
    trace_id: str


@dataclass(frozen=True)
class MinerUBatchSubmission:
    batch_id: str
    upload_urls: tuple[str, ...]
    provider_trace: MinerUProviderTrace


@dataclass(frozen=True)
class MinerUSourceState:
    source_id: str
    provider_file_name: str
    state: str
    full_zip_url: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class MinerUArtifact:
    source_id: str
    provider_file_name: str
    zip_bytes: bytes
    provider_trace_id: str


@dataclass(frozen=True)
class MinerUClientConfig:
    api_base_url: str = "https://mineru.net"
    model_version: str = "vlm"
    language: str = "ch"
    enable_table: bool = True
    enable_formula: bool = True
    is_ocr: bool = False
    poll_interval_seconds: float = 2.0
    deadline_seconds: float = 900.0
    max_result_bytes: int = 268435456
    allowed_download_hosts: tuple[str, ...] = (
        "cdn-mineru.openxlab.org.cn",
        "mineru.oss-cn-shanghai.aliyuncs.com",
    )
    max_poll_retries: int = 3

    def __post_init__(self) -> None:
        parsed = urlsplit(self.api_base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise MinerUProtocolError("MinerU API base URL must use HTTPS")
        host = parsed.hostname.lower()
        if host != "mineru.net" and not host.endswith(".mineru.net"):
            raise MinerUProtocolError("MinerU API base URL must use a mineru.net host")
        if self.deadline_seconds <= 0 or self.poll_interval_seconds < 0:
            raise MinerUProtocolError("MinerU polling settings are invalid")
        if self.max_result_bytes <= 0 or self.max_poll_retries < 0:
            raise MinerUProtocolError("MinerU transport limits are invalid")


class MinerUPrecisionClient:
    def __init__(
        self,
        *,
        token: str,
        config: MinerUClientConfig,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not token.strip():
            raise MinerUProviderError("MinerU API token is not configured")
        self._token = token.strip()
        self._config = config
        self._client = client
        self._sleep = sleep
        self._monotonic = monotonic
        self._api_base_url = config.api_base_url.rstrip("/")

    def extract(self, files: list[MinerUInput]) -> list[MinerUArtifact]:
        self._validate_inputs(files)
        submission = self._submit(files)
        for item, upload_url in zip(files, submission.upload_urls, strict=True):
            self._upload(item.path, upload_url)
        states, trace = self._poll_until_complete(submission.batch_id, files)
        return [self._download(state, trace) for state in states]

    def _validate_inputs(self, files: list[MinerUInput]) -> None:
        if not files:
            raise MinerUProtocolError("at least one MinerU input is required")
        if len(files) > 200:
            raise MinerUProtocolError("MinerU batch cannot exceed 200 files")
        source_ids = [item.source_id for item in files]
        if len(source_ids) != len(set(source_ids)):
            raise MinerUProtocolError("MinerU source ids must be unique")
        for item in files:
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", item.source_id):
                raise MinerUProtocolError("MinerU source id is invalid")
            if not item.path.is_file():
                raise MinerUProtocolError(f"MinerU input file is missing: {item.path.name}")

    def _submit(self, files: list[MinerUInput]) -> MinerUBatchSubmission:
        payload = {
            "files": [
                {
                    "name": item.path.name,
                    "data_id": item.source_id,
                    "is_ocr": self._config.is_ocr,
                }
                for item in files
            ],
            "model_version": self._config.model_version,
            "language": self._config.language,
            "enable_table": self._config.enable_table,
            "enable_formula": self._config.enable_formula,
        }
        response = self._api_request(
            "POST",
            f"{self._api_base_url}/api/v4/file-urls/batch",
            json=payload,
            timeout=API_TIMEOUT,
        )
        body = self._provider_body(response)
        data = self._required_dict(body, "data")
        batch_id = self._required_string(data, "batch_id")
        file_urls = data.get("file_urls")
        if not isinstance(file_urls, list) or not all(isinstance(url, str) and url for url in file_urls):
            raise MinerUProtocolError("MinerU response has invalid file_urls")
        if len(file_urls) != len(files):
            raise MinerUProtocolError("MinerU upload URL count does not match submitted file count")
        return MinerUBatchSubmission(
            batch_id=batch_id,
            upload_urls=tuple(file_urls),
            provider_trace=MinerUProviderTrace(self._required_string(body, "trace_id")),
        )

    def _upload(self, path: Path, upload_url: str) -> None:
        self._validate_https_url(upload_url, "signed upload")
        request = self._client.build_request(
            "PUT",
            upload_url,
            content=path.read_bytes(),
            timeout=UPLOAD_TIMEOUT,
        )
        request.headers.pop("authorization", None)
        try:
            response = self._client.send(request)
        except httpx.HTTPError as exc:
            raise MinerUProviderError(self._safe_message(f"signed upload failed: {exc}")) from exc
        if not 200 <= response.status_code < 300:
            raise MinerUProviderError(f"signed upload failed with HTTP {response.status_code}")

    def _poll_until_complete(
        self,
        batch_id: str,
        files: list[MinerUInput],
    ) -> tuple[list[MinerUSourceState], MinerUProviderTrace]:
        deadline = self._monotonic() + self._config.deadline_seconds
        expected_ids = [item.source_id for item in files]
        while True:
            if self._monotonic() >= deadline:
                raise MinerUTimeoutError("MinerU extraction deadline exceeded")
            response = self._poll_request(batch_id, deadline)
            body = self._provider_body(response)
            data = self._required_dict(body, "data")
            if self._required_string(data, "batch_id") != batch_id:
                raise MinerUProtocolError("MinerU polling batch id does not match")
            raw_results = data.get("extract_result")
            if not isinstance(raw_results, list):
                raise MinerUProtocolError("MinerU response has invalid extract_result")
            states = [self._parse_source_state(item) for item in raw_results]
            state_by_id = {item.source_id: item for item in states}
            if len(state_by_id) != len(states) or set(state_by_id) != set(expected_ids):
                raise MinerUProtocolError("MinerU result source ids do not match submitted source ids")
            ordered = [state_by_id[source_id] for source_id in expected_ids]
            for state in ordered:
                if state.state == "failed":
                    raise MinerUProviderError(
                        self._safe_message(
                            f"MinerU extraction failed for {state.source_id}: {state.error_message or 'provider failure'}"
                        )
                    )
                if state.state not in NONTERMINAL_STATES and state.state != "done":
                    raise MinerUProtocolError(f"unknown MinerU provider state: {state.state}")
            if all(state.state == "done" for state in ordered):
                for state in ordered:
                    if not state.full_zip_url:
                        raise MinerUProtocolError("completed MinerU result has no ZIP URL")
                return ordered, MinerUProviderTrace(self._required_string(body, "trace_id"))
            self._sleep(self._config.poll_interval_seconds)

    def _poll_request(self, batch_id: str, deadline: float) -> httpx.Response:
        url = f"{self._api_base_url}/api/v4/extract-results/batch/{batch_id}"
        retries = 0
        while True:
            try:
                response = self._api_request("GET", url, timeout=API_TIMEOUT, allow_status=True)
            except httpx.TransportError as exc:
                if retries >= self._config.max_poll_retries or self._monotonic() >= deadline:
                    raise MinerUProviderError(self._safe_message(f"MinerU polling failed: {exc}")) from exc
                retries += 1
                self._sleep(min(2**retries, 8))
                continue
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if retries >= self._config.max_poll_retries or self._monotonic() >= deadline:
                    raise MinerUProviderError(
                        f"MinerU polling failed after bounded retries: HTTP {response.status_code}"
                    )
                retries += 1
                self._sleep(min(2**retries, 8))
                continue
            if not 200 <= response.status_code < 300:
                raise MinerUProviderError(f"MinerU API rejected polling: HTTP {response.status_code}")
            return response

    def _parse_source_state(self, value: Any) -> MinerUSourceState:
        if not isinstance(value, dict):
            raise MinerUProtocolError("MinerU source result must be an object")
        return MinerUSourceState(
            source_id=self._required_string(value, "data_id"),
            provider_file_name=self._required_string(value, "file_name"),
            state=self._required_string(value, "state"),
            full_zip_url=str(value.get("full_zip_url") or "").strip(),
            error_message=str(value.get("err_msg") or "").strip(),
        )

    def _download(
        self,
        state: MinerUSourceState,
        trace: MinerUProviderTrace,
    ) -> MinerUArtifact:
        self._validate_download_url(state.full_zip_url)
        request = self._client.build_request("GET", state.full_zip_url, timeout=DOWNLOAD_TIMEOUT)
        request.headers.pop("authorization", None)
        try:
            response = self._client.send(request, stream=True)
            if not 200 <= response.status_code < 300:
                raise MinerUProviderError(f"MinerU ZIP download failed: HTTP {response.status_code}")
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self._config.max_result_bytes:
                raise MinerUProtocolError("MinerU ZIP exceeds the configured download limit")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > self._config.max_result_bytes:
                    raise MinerUProtocolError("MinerU ZIP exceeds the configured download limit")
                chunks.append(chunk)
        except MinerUError:
            raise
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise MinerUProviderError(self._safe_message(f"MinerU ZIP download failed: {exc}")) from exc
        finally:
            if "response" in locals():
                response.close()
        return MinerUArtifact(
            source_id=state.source_id,
            provider_file_name=state.provider_file_name,
            zip_bytes=b"".join(chunks),
            provider_trace_id=trace.trace_id,
        )

    def _api_request(
        self,
        method: str,
        url: str,
        *,
        timeout: httpx.Timeout,
        allow_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._token}"
        try:
            response = self._client.request(method, url, headers=headers, timeout=timeout, **kwargs)
        except httpx.HTTPError as exc:
            if allow_status:
                raise
            raise MinerUProviderError(
                self._safe_message(f"MinerU API request failed: {exc}")
            ) from exc
        if not allow_status and not 200 <= response.status_code < 300:
            raise MinerUProviderError(f"MinerU API request failed: HTTP {response.status_code}")
        return response

    def _provider_body(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except (ValueError, UnicodeError) as exc:
            raise MinerUProtocolError("MinerU API returned malformed JSON") from exc
        if not isinstance(body, dict):
            raise MinerUProtocolError("MinerU API response must be an object")
        code = body.get("code")
        if not isinstance(code, int) or isinstance(code, bool):
            raise MinerUProtocolError("MinerU API response code must be an integer")
        if code != 0:
            message = self._safe_message(str(body.get("msg") or "provider error"))
            raise MinerUProviderError(f"MinerU provider code {code}: {message}")
        return body

    @staticmethod
    def _required_dict(value: dict[str, Any], key: str) -> dict[str, Any]:
        result = value.get(key)
        if not isinstance(result, dict):
            raise MinerUProtocolError(f"MinerU response field {key} must be an object")
        return result

    @staticmethod
    def _required_string(value: dict[str, Any], key: str) -> str:
        result = value.get(key)
        if not isinstance(result, str) or not result.strip():
            raise MinerUProtocolError(f"MinerU response field {key} must be a non-empty string")
        return result.strip()

    @staticmethod
    def _validate_https_url(url: str, label: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise MinerUProtocolError(f"MinerU {label} URL must use HTTPS")

    def _validate_download_url(self, url: str) -> None:
        self._validate_https_url(url, "result download")
        host = (urlsplit(url).hostname or "").lower()
        allowed = {item.lower() for item in self._config.allowed_download_hosts}
        if host not in allowed:
            raise MinerUProtocolError("MinerU result download host is not approved")

    def _safe_message(self, message: str) -> str:
        redacted = message.replace(self._token, "[REDACTED]")

        def strip_query(match: re.Match[str]) -> str:
            parsed = urlsplit(match.group(0).rstrip(".,;"))
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

        return re.sub(r"https?://[^\s]+", strip_query, redacted)[:500]

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DEFAULT_CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"


class ProviderJSONError(ValueError):
    pass


def siliconflow_post(
    endpoint: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: int = 120,
    retries: int = 2,
    base_url: str = SILICONFLOW_BASE_URL,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    for attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code >= 500 and attempt < retries:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"SiliconFlow HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"SiliconFlow request failed: {exc}") from exc
        except TimeoutError as exc:
            if attempt < retries:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"SiliconFlow request timed out: {exc}") from exc

    raise RuntimeError("SiliconFlow request failed after retries")


def embed_texts(
    texts: list[str],
    api_key: str,
    model: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 24,
    base_url: str = SILICONFLOW_BASE_URL,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = siliconflow_post(
            "embeddings",
            {"model": model, "input": batch},
            api_key,
            base_url=base_url,
        )
        rows = response.get("data", [])
        if len(rows) != len(batch):
            raise RuntimeError("Embedding response length does not match request length")
        embeddings.extend(row["embedding"] for row in rows)
    return embeddings


def embedding_cache_key(model: str, text: str) -> str:
    payload = json.dumps(
        {"model": model, "text": text},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def embed_texts_cached(
    texts: list[str],
    api_key: str,
    model: str = DEFAULT_EMBED_MODEL,
    cache_path: Path | None = None,
    base_url: str = SILICONFLOW_BASE_URL,
) -> list[list[float]]:
    if cache_path is None:
        return _embed_texts_with_optional_base_url(
            texts,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    cache: dict[str, Any] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    embeddings: list[list[float] | None] = [None] * len(texts)
    missing_texts: list[str] = []
    missing_indexes: list[int] = []
    missing_keys: list[str] = []

    for index, text in enumerate(texts):
        key = embedding_cache_key(model, text)
        cached = cache.get(key)
        if isinstance(cached, dict) and isinstance(cached.get("embedding"), list):
            embeddings[index] = cached["embedding"]
            continue
        missing_texts.append(text)
        missing_indexes.append(index)
        missing_keys.append(key)

    if missing_texts:
        fetched = _embed_texts_with_optional_base_url(
            missing_texts,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        for index, key, embedding in zip(missing_indexes, missing_keys, fetched):
            embeddings[index] = embedding
            cache[key] = {
                "model": model,
                "dimensions": len(embedding),
                "embedding": embedding,
            }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    if any(embedding is None for embedding in embeddings):
        raise RuntimeError("Embedding cache failed to fill all requested texts")
    return [embedding for embedding in embeddings if embedding is not None]


def _embed_texts_with_optional_base_url(
    texts: list[str],
    api_key: str,
    model: str,
    base_url: str,
) -> list[list[float]]:
    if base_url == SILICONFLOW_BASE_URL:
        return embed_texts(texts, api_key=api_key, model=model)
    return embed_texts(texts, api_key=api_key, model=model, base_url=base_url)


def generate_markdown(
    messages: list[dict[str, str]],
    api_key: str,
    model: str = DEFAULT_CHAT_MODEL,
    base_url: str = SILICONFLOW_BASE_URL,
) -> str:
    response = siliconflow_post(
        "chat/completions",
        {
            "model": model,
            "messages": messages,
            "temperature": 0.15,
            "max_tokens": 6000,
        },
        api_key,
        timeout=240,
        retries=1,
        base_url=base_url,
    )
    try:
        return response["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected chat response shape: {response}") from exc


def generate_json_object(
    messages: list[dict[str, str]],
    api_key: str,
    model: str = DEFAULT_CHAT_MODEL,
    base_url: str = SILICONFLOW_BASE_URL,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.15,
        "max_tokens": 6000,
        "response_format": {"type": "json_object"},
    }
    if (
        urlsplit(base_url).hostname == "api.deepseek.com"
        and model in {"deepseek-v4-flash", "deepseek-v4-pro"}
    ):
        payload["thinking"] = {"type": "disabled"}
    response = siliconflow_post(
        "chat/completions",
        payload,
        api_key,
        timeout=240,
        retries=1,
        base_url=base_url,
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderJSONError("unexpected_response_shape") from exc
    if not isinstance(content, str):
        raise ProviderJSONError("unexpected_response_shape")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderJSONError("invalid_json") from exc
    if not isinstance(parsed, dict):
        raise ProviderJSONError("json_root_not_object")
    return parsed


def probe_siliconflow_provider(
    api_key: str,
    chat_model: str = DEFAULT_CHAT_MODEL,
    embed_model: str = DEFAULT_EMBED_MODEL,
    timeout: int = 15,
) -> dict[str, Any]:
    started = time.monotonic()
    checks: list[dict[str, str]] = []

    try:
        embedding_response = siliconflow_post(
            "embeddings",
            {"model": embed_model, "input": ["ping"]},
            api_key,
            timeout=timeout,
            retries=0,
        )
        rows = embedding_response.get("data", [])
        if not rows or not isinstance(rows[0].get("embedding"), list):
            raise RuntimeError("Unexpected embedding response shape")
        checks.append({"name": "embedding", "status": "ok", "detail": embed_model})
    except Exception as exc:
        checks.append({"name": "embedding", "status": "error", "detail": str(exc)[:200]})

    try:
        chat_response = siliconflow_post(
            "chat/completions",
            {
                "model": chat_model,
                "messages": [{"role": "user", "content": "ping"}],
                "temperature": 0,
                "max_tokens": 1,
            },
            api_key,
            timeout=timeout,
            retries=0,
        )
        choices = chat_response.get("choices", [])
        if not choices:
            raise RuntimeError("Unexpected chat response shape")
        checks.append({"name": "chat", "status": "ok", "detail": chat_model})
    except Exception as exc:
        checks.append({"name": "chat", "status": "error", "detail": str(exc)[:200]})

    status = "ok" if all(check["status"] == "ok" for check in checks) else "error"
    elapsed_ms = int((time.monotonic() - started) * 1000)
    detail = "chat and embedding reachable" if status == "ok" else "provider probe failed"
    return {
        "name": "provider_connectivity",
        "status": status,
        "detail": detail,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
    }

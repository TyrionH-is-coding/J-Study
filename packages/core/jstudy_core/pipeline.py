from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from packages.domains.medicine import (
    StudyQuery,
    audit_output_quality,
    build_generation_prompt,
    build_study_queries,
    extract_evidence_refs,
    parse_mnemonics,
    retrieve_mnemonics,
)
from packages.parsers.pymupdf_parser import extract_pdf_pages
from packages.retrieval.hybrid import (
    Chunk,
    DeepTutorRagAdapter,
    RagConfig,
    chunk_pages,
    cosine_similarity,
    filter_ranked_chunks,
    is_low_value_chunk,
    load_rag_config,
    reciprocal_rank_fusion,
    select_evidence_chunks,
)


DEFAULT_CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def build_evidence_items(chunks: list[Chunk], source_file: str) -> list[dict[str, Any]]:
    evidence = []
    for idx, chunk in enumerate(chunks, start=1):
        item = {
            "id": f"E{idx:03d}",
            "source_file": source_file,
            "page": chunk.page,
            "chunk_id": chunk.id,
            "score": round(chunk.score, 4),
            "excerpt": chunk.text[:500],
        }
        if chunk.query_id:
            item["query_id"] = chunk.query_id
        if chunk.query_title:
            item["query_title"] = chunk.query_title
        if chunk.retrieval_method:
            item["retrieval_method"] = chunk.retrieval_method
        evidence.append(item)
    return evidence


def read_api_key(path: Path) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"API key file is empty: {path}")
    return key


def siliconflow_post(
    endpoint: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: int = 120,
    retries: int = 2,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"{SILICONFLOW_BASE_URL}/{endpoint.lstrip('/')}"

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
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = siliconflow_post(
            "embeddings",
            {"model": model, "input": batch},
            api_key,
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
) -> list[list[float]]:
    if cache_path is None:
        return embed_texts(texts, api_key=api_key, model=model)

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
        fetched = embed_texts(missing_texts, api_key=api_key, model=model)
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


def retrieve_chunks(
    query: str,
    chunks: list[Chunk],
    chunk_embeddings: list[list[float]],
    api_key: str,
    model: str = DEFAULT_EMBED_MODEL,
    top_k: int = 18,
) -> list[Chunk]:
    query_embedding = embed_texts([query], api_key=api_key, model=model)[0]
    scored = [
        replace(
            chunk,
            score=cosine_similarity(query_embedding, embedding),
            embedding_index=index,
        )
        for index, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings))
    ]
    return sorted(scored, key=lambda chunk: chunk.score, reverse=True)[:top_k]


def generate_markdown(
    messages: list[dict[str, str]],
    api_key: str,
    model: str = DEFAULT_CHAT_MODEL,
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
    )
    try:
        return response["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected chat response shape: {response}") from exc


def build_evidence_links(markdown: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_id = {str(item.get("id")): item for item in evidence if item.get("id")}
    occurrence_counts: dict[str, int] = {}
    links: list[dict[str, Any]] = []

    for comment_index, match in enumerate(
        re.finditer(r"<!--\s*evidence:\s*([^>]+?)\s*-->", markdown, re.IGNORECASE),
        start=1,
    ):
        for ref_id in re.findall(r"\bE\d{3}\b", match.group(1)):
            item = evidence_by_id.get(ref_id)
            if item is None:
                continue
            occurrence_counts[ref_id] = occurrence_counts.get(ref_id, 0) + 1
            links.append(
                {
                    "ref_id": ref_id,
                    "occurrence": occurrence_counts[ref_id],
                    "comment_index": comment_index,
                    "target": {
                        "source_file": item.get("source_file", ""),
                        "page": item.get("page", ""),
                        "chunk_id": item.get("chunk_id", ""),
                        "quote": item.get("excerpt", ""),
                    },
                }
            )

    return links


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_mvp(
    pdf_path: Path,
    soul_path: Path,
    mnemonics_path: Path,
    api_key_path: Path,
    output_dir: Path,
    chat_model: str,
    embed_model: str,
    output_prefix: str = "mvp",
    rag_config: RagConfig | None = None,
    embedding_cache_path: Path | None = None,
    outline_path: Path | None = None,
) -> dict[str, Path]:
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    api_key = read_api_key(api_key_path)
    pages = extract_pdf_pages(pdf_path)
    chunks = chunk_pages(
        pages,
        max_chars=rag_config.chunk_max_chars,
        overlap=rag_config.chunk_overlap,
    )
    if not chunks:
        raise RuntimeError("No text chunks extracted from PDF")

    chunk_embeddings = embed_texts_cached(
        [chunk.text for chunk in chunks],
        api_key=api_key,
        model=embed_model,
        cache_path=embedding_cache_path,
    )

    study_queries = build_study_queries()
    query_embeddings = embed_texts_cached(
        [study_query.query for study_query in study_queries],
        api_key=api_key,
        model=embed_model,
        cache_path=embedding_cache_path,
    )

    selected_chunks, retrieval_trace = select_evidence_chunks(
        study_queries,
        chunks,
        chunk_embeddings,
        query_embeddings,
        rag_config,
    )

    evidence = build_evidence_items(selected_chunks, pdf_path.name)
    mnemonics = parse_mnemonics(mnemonics_path.read_text(encoding="utf-8"))
    retrieval_query = "\n".join(study_query.query for study_query in study_queries)
    mnemonic_hits = retrieve_mnemonics(
        retrieval_query + "\n" + "\n".join(chunk.text for chunk in selected_chunks),
        mnemonics,
        limit=rag_config.mnemonic_limit,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = output_dir / f"{output_prefix}-chunks.json"
    trace_path = output_dir / f"{output_prefix}-retrieval_trace.json"
    evidence_path = output_dir / f"{output_prefix}-evidence.json"
    evidence_links_path = output_dir / f"{output_prefix}-evidence_links.json"
    markdown_path = output_dir / f"{output_prefix}-output.md"
    quality_path = output_dir / f"{output_prefix}-quality.json"

    write_json(
        chunks_path,
        [
            {
                **asdict(chunk),
                "embedding_saved": False,
            }
            for chunk in chunks
        ],
    )
    write_json(
        trace_path,
        {
            "pdf": str(pdf_path),
            "chat_model": chat_model,
            "embed_model": embed_model,
            "rag_config": asdict(rag_config),
            "embedding_cache": str(embedding_cache_path),
            "retrieval_strategy": "deeptutor-style multi-query hybrid reciprocal-rank fusion",
            "study_queries": [asdict(study_query) for study_query in study_queries],
            "retrieval_query_text": retrieval_query,
            "selected_chunks": [asdict(chunk) for chunk in selected_chunks],
            "query_traces": retrieval_trace,
            "mnemonic_hits": mnemonic_hits,
        },
    )
    write_json(evidence_path, evidence)

    messages = build_generation_prompt(
        soul_path.read_text(encoding="utf-8"),
        evidence,
        mnemonic_hits,
        outline=outline_path.read_text(encoding="utf-8") if outline_path else "",
    )
    markdown = generate_markdown(messages, api_key=api_key, model=chat_model)
    markdown_path.write_text(markdown + "\n", encoding="utf-8")
    write_json(evidence_links_path, build_evidence_links(markdown, evidence))
    write_json(quality_path, audit_output_quality(markdown, evidence))

    return {
        "chunks": chunks_path,
        "trace": trace_path,
        "evidence": evidence_path,
        "evidence_links": evidence_links_path,
        "markdown": markdown_path,
        "quality": quality_path,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = PROJECT_ROOT
    parser = argparse.ArgumentParser(description="Run the single-courseware DeepTutor MVP.")
    parser.add_argument("--pdf", type=Path, default=root / "12-球菌.pdf")
    parser.add_argument("--soul", type=Path, default=root / "soul.md")
    parser.add_argument("--mnemonics", type=Path, default=root / "mnemonics.md")
    parser.add_argument("--api-key", type=Path, default=root / "siliconflow api key.txt")
    parser.add_argument("--outline", type=Path)
    parser.add_argument("--output-dir", type=Path, default=root)
    parser.add_argument("--output-prefix", default="mvp")
    parser.add_argument("--chat-model", default=os.getenv("SILICONFLOW_CHAT_MODEL", DEFAULT_CHAT_MODEL))
    parser.add_argument("--embed-model", default=os.getenv("SILICONFLOW_EMBED_MODEL", DEFAULT_EMBED_MODEL))
    parser.add_argument("--rag-config", type=Path)
    parser.add_argument("--embedding-cache", type=Path, default=root / ".mvp_cache" / "embeddings.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    outputs = run_mvp(
        pdf_path=args.pdf,
        soul_path=args.soul,
        mnemonics_path=args.mnemonics,
        api_key_path=args.api_key,
        output_dir=args.output_dir,
        chat_model=args.chat_model,
        embed_model=args.embed_model,
        output_prefix=args.output_prefix,
        rag_config=load_rag_config(args.rag_config),
        embedding_cache_path=args.embedding_cache,
        outline_path=args.outline,
    )
    print("MVP outputs:")
    for name, path in outputs.items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

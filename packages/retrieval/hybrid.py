from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

from packages.domains.medicine import StudyQuery


@dataclass(frozen=True)
class Chunk:
    id: str
    page: int
    text: str
    score: float = 0.0
    embedding_index: int | None = None
    query_id: str | None = None
    query_title: str | None = None
    retrieval_method: str | None = None
    source_id: str = ""
    source_file: str = ""


@dataclass(frozen=True)
class RagConfig:
    chunk_max_chars: int = 512
    chunk_overlap: int = 50
    top_k_candidates: int = 14
    per_query_limit: int = 2
    mnemonic_limit: int = 6

    def __post_init__(self) -> None:
        for name in ("chunk_max_chars", "top_k_candidates", "per_query_limit", "mnemonic_limit"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if self.chunk_overlap >= self.chunk_max_chars:
            raise ValueError("chunk_overlap must be smaller than chunk_max_chars")


def load_rag_config(path: Path | None) -> RagConfig:
    if path is None:
        return RagConfig()

    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(RagConfig)}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise RuntimeError(f"Unknown RAG config keys: {', '.join(unknown)}")
    return RagConfig(**data)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_pages(
    pages: list[dict[str, Any]],
    max_chars: int = 512,
    overlap: int = 50,
    source_id: str = "",
    source_file: str = "",
) -> list[Chunk]:
    chunks: list[Chunk] = []

    for page in pages:
        page_no = int(page["page"])
        text = normalize_text(str(page.get("text", "")))
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_number = len(chunks) + 1
                chunk_id = f"C{chunk_number:03d}"
                if source_id:
                    chunk_id = f"{source_id}-{chunk_id}"
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        page=page_no,
                        text=chunk_text,
                        embedding_index=len(chunks),
                        source_id=source_id,
                        source_file=source_file,
                    )
                )
            if end == len(text):
                break
            start = max(end - overlap, start + 1)

    return chunks


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def tokenize_for_bm25(text: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"[\u4e00-\u9fff]+|[A-Za-z0-9+\-.]+", text.lower()):
        value = match.group(0)
        if re.fullmatch(r"[\u4e00-\u9fff]+", value):
            if len(value) == 1:
                tokens.append(value)
                continue
            for ngram_size in (2, 3):
                if len(value) >= ngram_size:
                    tokens.extend(
                        value[index : index + ngram_size]
                        for index in range(len(value) - ngram_size + 1)
                    )
        else:
            tokens.append(value)
    return tokens


def bm25_scores(query: str, chunks: list[Chunk]) -> dict[str, float]:
    query_terms = tokenize_for_bm25(query)
    if not query_terms or not chunks:
        return {chunk.id: 0.0 for chunk in chunks}

    documents = [tokenize_for_bm25(chunk.text) for chunk in chunks]
    doc_count = len(documents)
    avg_len = sum(len(document) for document in documents) / max(1, doc_count)
    document_frequency: dict[str, int] = {}
    for document in documents:
        for term in set(document):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    k1 = 1.5
    b = 0.75
    scores: dict[str, float] = {}
    for chunk, document in zip(chunks, documents):
        term_counts: dict[str, int] = {}
        for term in document:
            term_counts[term] = term_counts.get(term, 0) + 1
        doc_len = len(document) or 1
        score = 0.0
        for term in query_terms:
            frequency = term_counts.get(term, 0)
            if frequency == 0:
                continue
            df = document_frequency.get(term, 0)
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * doc_len / max(1.0, avg_len))
            score += idf * frequency * (k1 + 1) / denominator
        scores[chunk.id] = score
    return scores


def reciprocal_rank_fusion(
    query: str,
    chunks: list[Chunk],
    vector_scores: dict[str, float],
    rank_constant: int = 60,
) -> list[Chunk]:
    lexical_scores = bm25_scores(query, chunks)
    vector_ranked = sorted(chunks, key=lambda chunk: vector_scores.get(chunk.id, 0.0), reverse=True)
    lexical_ranked = sorted(chunks, key=lambda chunk: lexical_scores.get(chunk.id, 0.0), reverse=True)
    vector_ranks = {chunk.id: rank for rank, chunk in enumerate(vector_ranked, start=1)}
    lexical_ranks = {chunk.id: rank for rank, chunk in enumerate(lexical_ranked, start=1)}

    fused = []
    for chunk in chunks:
        score = 1 / (rank_constant + vector_ranks[chunk.id])
        if lexical_scores.get(chunk.id, 0.0) > 0:
            score += 2 / (rank_constant + lexical_ranks[chunk.id])
        fused.append(replace(chunk, score=score, retrieval_method="hybrid_rrf"))
    return sorted(fused, key=lambda chunk: chunk.score, reverse=True)


def is_low_value_chunk(text: str) -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < 28:
        return True
    heading_patterns = [
        r"^[一二三四五六七八九十]+[、.．]\s*[\u4e00-\u9fff\sA-Za-z]+$",
        r"^\d+\s+[\u4e00-\u9fff\sA-Za-z]+$",
    ]
    if len(cleaned) < 55 and any(re.match(pattern, cleaned) for pattern in heading_patterns):
        return True
    if (
        len(cleaned) < 90
        and re.match(r"^[一二三四五六七八九十]+[、.．]", cleaned)
        and "生物学性状" in cleaned
        and not any(marker in cleaned for marker in ("形态", "染色", "培养", "致病", "疾病", "试验", "阳性", "阴性"))
    ):
        return True
    detail_markers = [
        "：",
        ":",
        "+",
        "-",
        "（",
        "(",
        "试验",
        "感染",
        "毒素",
        "培养",
        "阳性",
        "阴性",
        "疾病",
        "检查",
    ]
    if len(cleaned) < 70 and not any(marker in cleaned for marker in detail_markers):
        return True
    return False


def has_required_term(text: str, required_any: tuple[str, ...]) -> bool:
    if not required_any:
        return True
    lowered = normalize_text(text).lower()
    return any(term.lower() in lowered for term in required_any)


def filter_ranked_chunks(
    chunks: list[Chunk],
    per_query_limit: int,
    seen_chunk_ids: set[str] | None = None,
    required_any: tuple[str, ...] = (),
) -> list[Chunk]:
    seen = seen_chunk_ids if seen_chunk_ids is not None else set()
    filtered: list[Chunk] = []
    seen_texts: set[str] = set()

    for chunk in chunks:
        if chunk.id in seen:
            continue
        text_key = normalize_text(chunk.text[:180]).lower()
        if text_key in seen_texts:
            continue
        if is_low_value_chunk(chunk.text):
            continue
        if not has_required_term(chunk.text, required_any):
            continue
        filtered.append(chunk)
        seen.add(chunk.id)
        seen_texts.add(text_key)
        if len(filtered) >= per_query_limit:
            break

    return filtered


def retrieve_chunks_hybrid(
    study_query: StudyQuery,
    query_embedding: list[float],
    chunks: list[Chunk],
    chunk_embeddings: list[list[float]],
    top_k: int,
) -> list[Chunk]:
    vector_scores = {
        chunk.id: cosine_similarity(query_embedding, embedding)
        for chunk, embedding in zip(chunks, chunk_embeddings)
    }
    ranked = reciprocal_rank_fusion(study_query.query, chunks, vector_scores)
    return [
        replace(chunk, query_id=study_query.id, query_title=study_query.title)
        for chunk in ranked[:top_k]
    ]


class DeepTutorRagAdapter:
    """Local MVP adapter shaped like DeepTutor's RAGService.search result."""

    provider = "local_hybrid_rrf"

    def __init__(
        self,
        chunks: list[Chunk],
        chunk_embeddings: list[list[float]],
        source_file: str,
        rag_config: RagConfig,
    ) -> None:
        self.chunks = chunks
        self.chunk_embeddings = chunk_embeddings
        self.source_file = source_file
        self.rag_config = rag_config

    def retrieve(
        self,
        study_query: StudyQuery,
        query_embedding: list[float],
        seen_chunk_ids: set[str] | None = None,
    ) -> tuple[list[Chunk], dict[str, Any]]:
        ranked = retrieve_chunks_hybrid(
            study_query,
            query_embedding,
            self.chunks,
            self.chunk_embeddings,
            top_k=min(self.rag_config.top_k_candidates, len(self.chunks)),
        )
        filtered = filter_ranked_chunks(
            ranked,
            per_query_limit=self.rag_config.per_query_limit,
            seen_chunk_ids=seen_chunk_ids,
            required_any=study_query.required_any,
        )
        trace = {
            "query": asdict(study_query),
            "kept": [asdict(chunk) for chunk in filtered],
            "top_candidates": [asdict(chunk) for chunk in ranked[:8]],
        }
        return filtered, trace

    def search(
        self,
        study_query: StudyQuery,
        query_embedding: list[float],
        seen_chunk_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        chunks, trace = self.retrieve(study_query, query_embedding, seen_chunk_ids)
        content = "\n\n".join(chunk.text for chunk in chunks)
        sources = [
            {
                "title": self.source_file or f"Document {index}",
                "content": chunk.text[:200],
                "source": chunk.source_file or self.source_file,
                "source_id": chunk.source_id,
                "source_file": chunk.source_file or self.source_file,
                "page": chunk.page,
                "chunk_id": chunk.id,
                "score": round(chunk.score, 4),
                "query_id": chunk.query_id,
                "query_title": chunk.query_title,
                "retrieval_method": chunk.retrieval_method,
            }
            for index, chunk in enumerate(chunks, start=1)
        ]
        return {
            "query": study_query.query,
            "answer": content,
            "content": content,
            "sources": sources,
            "provider": self.provider,
            "trace": trace,
        }


def select_evidence_chunks(
    study_queries: list[StudyQuery],
    chunks: list[Chunk],
    chunk_embeddings: list[list[float]],
    query_embeddings: list[list[float]],
    rag_config: RagConfig,
) -> tuple[list[Chunk], list[dict[str, Any]]]:
    adapter = DeepTutorRagAdapter(
        chunks=chunks,
        chunk_embeddings=chunk_embeddings,
        source_file="",
        rag_config=rag_config,
    )
    selected_chunks: list[Chunk] = []
    seen_chunk_ids: set[str] = set()
    retrieval_trace: list[dict[str, Any]] = []

    for study_query, query_embedding in zip(study_queries, query_embeddings):
        filtered, trace = adapter.retrieve(
            study_query,
            query_embedding,
            seen_chunk_ids=seen_chunk_ids,
        )
        selected_chunks.extend(filtered)
        retrieval_trace.append(trace)

    return selected_chunks, retrieval_trace

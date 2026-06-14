from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import fitz


DEFAULT_CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


@dataclass(frozen=True)
class StudyQuery:
    id: str
    title: str
    query: str
    required_any: tuple[str, ...] = ()


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
                chunks.append(
                    Chunk(
                        id=f"C{len(chunks) + 1:03d}",
                        page=page_no,
                        text=chunk_text,
                        embedding_index=len(chunks),
                    )
                )
            if end == len(text):
                break
            start = max(end - overlap, start + 1)

    return chunks


def build_study_queries() -> list[StudyQuery]:
    """Queries for the single-courseware cocci MVP.

    DeepTutor's tool layer can call RAG multiple times. The MVP mirrors that
    pattern by searching each learning module separately instead of issuing one
    broad query for the whole lecture.
    """

    return [
        StudyQuery(
            "overview",
            "体系概览",
            "病原性球菌 化脓性球菌 革兰阳性球菌 革兰阴性球菌 分类 葡萄球菌 链球菌 奈瑟菌",
            ("病原性球菌", "化脓性球菌", "革兰阳性", "革兰阴性"),
        ),
        StudyQuery(
            "staphylococcus_basic",
            "葡萄球菌：基本特征",
            "葡萄球菌 生物学性状 形态 染色 葡萄串状 革兰阳性 触酶 catalase 培养特性",
            ("葡萄球菌", "staphylococci", "staphylococcus", "触酶"),
        ),
        StudyQuery(
            "staphylococcus_virulence",
            "葡萄球菌：致病物质",
            "葡萄球菌 致病物质 凝固酶 耐热核酸酶 透明质酸酶 脂酶 β内酰胺酶 溶血素 肠毒素 TSST 表皮剥脱毒素",
            ("葡萄球菌", "staphylococcal", "凝固酶", "coagulase", "tsst", "肠毒素"),
        ),
        StudyQuery(
            "staphylococcus_disease",
            "葡萄球菌：所致疾病",
            "葡萄球菌 所致疾病 侵袭性感染 化脓性感染 食物中毒 SSSS TSS 假膜性肠炎",
            ("葡萄球菌", "staphylococcal", "食物中毒", "ssss", "tss", "肠毒素"),
        ),
        StudyQuery(
            "staphylococcus_lab",
            "葡萄球菌：微生物学检查",
            "葡萄球菌 微生物学检查 标本采集 直接涂片 革兰染色 分离培养 鉴定 凝固酶 耐热核酸酶 甘露醇 MALDI TOF",
            ("凝固酶", "耐热核酸酶", "甘露醇", "maldi", "金黄色", "类似葡萄球菌属"),
        ),
        StudyQuery(
            "streptococcus_basic",
            "链球菌：基本特征与分类",
            "链球菌 生物学性状 链状排列 革兰阳性 触酶阴性 溶血分类 α溶血 β溶血 γ溶血",
            ("传统的分类", "根据溶血", "β溶血性链球菌", "γ溶血", "草绿色溶血链球菌"),
        ),
        StudyQuery(
            "streptococcus_virulence_disease",
            "A群链球菌：致病物质与疾病",
            "A群链球菌 化脓链球菌 致病物质 M蛋白 SLO SLS 致热外毒素 透明质酸酶 链激酶 链道酶 猩红热 风湿热 急性肾小球肾炎",
            ("A群链球菌", "化脓链球菌", "m蛋白", "slo", "sls", "致热外毒素", "streptolysin", "pyogenes"),
        ),
        StudyQuery(
            "streptococcus_lab",
            "链球菌：微生物学检查",
            "β溶血性链球菌 微生物学检查 标本 直接涂片 分离培养 血琼脂平板 ASO 抗链球菌溶血素O 风湿热",
            ("链球菌", "aso", "抗链球菌", "β", "溶血"),
        ),
        StudyQuery(
            "pneumococcus",
            "肺炎链球菌",
            "肺炎链球菌 生物学性状 荚膜 矛头状 α溶血 自溶 Optochin 胆汁溶菌 菊糖发酵 大叶性肺炎 铁锈色痰",
            ("肺炎链球菌", "pneumoniae", "optochin", "胆汁", "菊糖", "荚膜", "大叶性肺炎"),
        ),
        StudyQuery(
            "neisseria_overview",
            "奈瑟菌属概述",
            "奈瑟菌属 奈瑟菌科 革兰阴性双球菌 无鞭毛 无芽胞 菌毛 氧化酶 触酶 巧克力平板 CO2 脑膜炎奈瑟菌 淋病奈瑟菌",
            ("奈瑟菌", "neisseria", "革兰阴性双球菌", "脑膜炎奈瑟菌", "淋病奈瑟菌"),
        ),
        StudyQuery(
            "meningococcus_basic",
            "脑膜炎奈瑟菌：基本特征",
            "脑膜炎奈瑟菌 生物学性状 肾形 豆形 革兰阴性双球菌 荚膜 菌毛 自溶 抵抗力弱 5% CO2",
            ("肾形", "豆形", "自溶", "fragile", "5% co2", "5～10%co2"),
        ),
        StudyQuery(
            "meningococcus_pathogenicity",
            "脑膜炎奈瑟菌：致病性",
            "脑膜炎奈瑟菌 致病性 荚膜 菌毛 内毒素 流行性脑脊髓膜炎 13 groups A群",
            ("内毒素", "流行性脑脊髓膜炎", "13 groups", "serotypes", "荚膜和菌毛"),
        ),
        StudyQuery(
            "gonococcus",
            "淋病奈瑟菌",
            "淋病奈瑟菌 淋球菌 柱状上皮 菌毛 黏附 吞饮入胞 尿道脓性分泌物 潜伏感染 微生物学检查 抵抗力",
            ("淋病奈瑟菌", "gonorrhoeae", "淋球菌", "尿道", "宫颈"),
        ),
    ]


def parse_mnemonics(text: str) -> list[dict[str, Any]]:
    blocks = [block.strip() for block in re.split(r"(?m)^---\s*$", text) if block.strip()]
    mnemonics: list[dict[str, Any]] = []

    for block in blocks:
        item: dict[str, Any] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            item[key.strip()] = value.strip()

        if "keywords" in item:
            item["keywords"] = [
                keyword.strip()
                for keyword in str(item["keywords"]).split(",")
                if keyword.strip()
            ]

        if item.get("id") and item.get("content"):
            item.setdefault("source", "待审核候选")
            item.setdefault("keywords", [])
            mnemonics.append(item)

    return mnemonics


def retrieve_mnemonics(
    query: str,
    mnemonics: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    query_text = query.lower()

    for item in mnemonics:
        score = 0
        for keyword in item.get("keywords", []):
            if str(keyword).lower() in query_text:
                score += 3

        title = str(item.get("title", "")).lower()
        content = str(item.get("content", "")).lower()
        if title and title in query_text:
            score += 2
        if content and any(token in content for token in query_text.split()[:20]):
            score += 1

        if score > 0:
            copied = dict(item)
            copied["score"] = score
            scored.append(copied)

    return sorted(scored, key=lambda row: (-int(row["score"]), str(row["id"])))[:limit]


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


def extract_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = normalize_text(page.get_text("text"))
            if text:
                pages.append({"page": page_index, "text": text})
    return pages


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
                "source": self.source_file,
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


def build_generation_prompt(
    soul: str,
    evidence: list[dict[str, Any]],
    mnemonics: list[dict[str, Any]],
    outline: str = "",
) -> list[dict[str, str]]:
    grouped_evidence: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        grouped_evidence.setdefault(str(item.get("query_title") or "综合证据"), []).append(item)
    evidence_blocks = []
    for title, items in grouped_evidence.items():
        body = "\n\n".join(
            f"[{item['id']}] page {item['page']} chunk {item['chunk_id']}"
            f" score={item.get('score', '')}\n{item['excerpt'][:360]}"
            for item in items
        )
        evidence_blocks.append(f"### {title}\n\n{body}")
    evidence_text = "\n\n".join(evidence_blocks)
    mnemonic_text = "\n".join(
        f"- {item['title']}（{item['source']}）：{item['content']}"
        for item in mnemonics
    ) or "无命中口诀。"
    outline_text = outline.strip()
    outline_block = (
        f"下面是用户上传的课程大纲参考；如果它和课件证据冲突，以课件证据为准，但组织顺序优先参考大纲：\n{outline_text[:8000]}"
        if outline_text
        else "用户未上传课程大纲，本次按课件严格模式组织。"
    )

    system = (
        "你是面向医学生的课件整理助手。严格遵守用户提供的 soul.md。"
        "正文应像高质量学习资料，不要展示工程调试痕迹。"
    )
    user = f"""
下面是 soul.md 规则：

{soul}

下面是从当前课件检索出的证据片段，已经按学习模块分组。只能把这些片段支持的内容写成课件事实；如果某个细节没有证据，不要用常识补写。

{evidence_text}

课程大纲参考：

{outline_block}

下面是口诀库检索命中。口诀不是事实来源，必须按来源状态标注。

{mnemonic_text}

请基于以上内容生成一份单课件 MVP 学习资料。

硬性要求：
1. 使用“课件严格模式”。
2. 输出 Markdown。
3. 使用表格、Directory tree、竖向流程箭头三种形式，但不要为了形式而形式。
4. 关键知识点附近保留隐藏证据注释，例如 `<!-- evidence: E001 E002 -->`。
5. 缩写第一次出现必须写中文名、英文全称和缩写。
6. 口诀只在确实相关的位置出现。口诀来源必须用学生可见的正文标注，例如“来源：待审核候选”；不要用 HTML 注释隐藏口诀来源。
7. 每个主要小节都要尽量引用本小节对应 evidence；不要把一个 evidence 挪去支撑无关小节。
8. 关键鉴别表只能使用 evidence 明确出现的鉴别点；不要补写 evidence 中没有出现的糖发酵结果、年龄分布、流行病学细节或额外检查项。
9. 不要写“根据证据片段”“本 MVP”等工程化表达。
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


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


def extract_evidence_refs(markdown: str) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"<!--\s*evidence:\s*([^>]+?)\s*-->", markdown, re.IGNORECASE):
        refs.update(re.findall(r"\bE\d{3}\b", match.group(1)))
    return refs


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


def audit_output_quality(markdown: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_ids = {str(item.get("id")) for item in evidence if item.get("id")}
    referenced_ids = extract_evidence_refs(markdown)
    unknown_refs = sorted(referenced_ids - evidence_ids)
    unused_evidence = sorted(evidence_ids - referenced_ids)
    issues: list[dict[str, Any]] = []

    if not referenced_ids:
        issues.append(
            {
                "code": "missing_evidence_refs",
                "severity": "error",
                "message": "No hidden evidence comments were found in the generated markdown.",
            }
        )
    if unknown_refs:
        issues.append(
            {
                "code": "unknown_evidence_refs",
                "severity": "error",
                "message": "Generated markdown references evidence ids that do not exist.",
                "ids": unknown_refs,
            }
        )

    engineering_terms = ["MVP", "根据证据片段", "证据片段", "工程"]
    matched_terms = [term for term in engineering_terms if term in markdown]
    if matched_terms:
        issues.append(
            {
                "code": "engineering_language",
                "severity": "error",
                "message": "Generated markdown contains implementation-facing wording.",
                "terms": matched_terms,
            }
        )

    if unused_evidence:
        issues.append(
            {
                "code": "unused_evidence",
                "severity": "warning",
                "message": "Some retrieved evidence ids were not cited in the markdown.",
                "ids": unused_evidence,
            }
        )

    status = "fail" if any(issue["severity"] == "error" for issue in issues) else "pass"
    return {
        "status": status,
        "metrics": {
            "evidence_count": len(evidence_ids),
            "referenced_evidence_count": len(referenced_ids),
            "issue_count": len(issues),
        },
        "unknown_evidence_refs": unknown_refs,
        "unused_evidence": unused_evidence,
        "issues": issues,
    }


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

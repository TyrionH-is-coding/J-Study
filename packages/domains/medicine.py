from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StudyQuery:
    id: str
    title: str
    query: str
    required_any: tuple[str, ...] = ()


FALLBACK_TOPICS = ("医学", "核心概念", "机制", "分类", "诊断", "治疗", "检查", "考点")
STOP_TERMS = {
    "第一章",
    "第二章",
    "第三章",
    "第四章",
    "第五章",
    "第六章",
    "第七章",
    "第八章",
    "第九章",
    "第十章",
    "绪论",
    "目录",
    "课件",
    "课程",
    "学习目标",
    "教学目标",
    "重点",
    "难点",
    "小结",
}


def build_study_queries(source_text: str = "", outline: str = "") -> list[StudyQuery]:
    """Build RAG queries from the current upload instead of a fixed lecture topic."""

    topics = extract_study_topics(source_text=source_text, outline=outline)
    topic_text = " ".join(topics)
    required_any = tuple(topics[:8])

    return [
        StudyQuery(
            "overview",
            "体系概览",
            f"{topic_text} 课程结构 体系概览 核心概念 总结",
            required_any,
        ),
        StudyQuery(
            "key_concepts",
            "核心概念",
            f"{topic_text} 定义 概念 特点 组成 分类",
            required_any,
        ),
        StudyQuery(
            "mechanisms",
            "机制与流程",
            f"{topic_text} 机制 原理 流程 步骤 调控 发生发展",
            required_any,
        ),
        StudyQuery(
            "comparisons",
            "分类与鉴别",
            f"{topic_text} 分类 比较 区别 鉴别 表格 易混点",
            required_any,
        ),
        StudyQuery(
            "clinical_lab",
            "临床与检查",
            f"{topic_text} 临床表现 诊断 检查 实验 治疗 预防",
            required_any,
        ),
        StudyQuery(
            "exam_review",
            "复习与考点",
            f"{topic_text} 高频考点 记忆 易错点 总结 复习",
            required_any,
        ),
    ]


def extract_study_topics(source_text: str = "", outline: str = "", limit: int = 12) -> list[str]:
    outline_terms = _topic_candidates(outline)
    source_terms = _topic_candidates(source_text)
    ranked_source_terms = [term for term, _count in Counter(source_terms).most_common(limit * 2)]
    topics = _dedupe_terms([*outline_terms, *ranked_source_terms])
    return topics[:limit] or list(FALLBACK_TOPICS)


def _topic_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        cleaned = _clean_topic_line(line)
        if cleaned:
            candidates.extend(_split_topic_terms(cleaned))
    if not candidates:
        candidates.extend(_split_topic_terms(text))
    return [term for term in candidates if _is_topic_term(term)]


def _clean_topic_line(line: str) -> str:
    cleaned = re.sub(r"^\s*(第[一二三四五六七八九十百\d]+[章节篇编]\s*)", "", line.strip())
    cleaned = re.sub(r"^\s*[\d０-９]+[、.．)]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -—:：；;，,。.")


def _split_topic_terms(text: str) -> list[str]:
    return [
        part.strip(" -—:：；;，,。.()（）[]【】")
        for part in re.split(r"[\s,，;；、/|]+", text)
        if part.strip()
    ]


def _is_topic_term(term: str) -> bool:
    if term in STOP_TERMS:
        return False
    if len(term) < 2 or len(term) > 24:
        return False
    if term.isdigit():
        return False
    # 过滤英文停用词和课程代码
    if term.lower() in {"the", "a", "an", "this", "that", "these", "those", "is", "are", "was", "were",
                        "be", "been", "being", "have", "has", "had", "do", "does", "did",
                        "will", "would", "can", "could", "shall", "should", "may", "might",
                        "must", "to", "of", "in", "for", "on", "with", "at", "by", "from",
                        "as", "into", "through", "during", "before", "after", "above", "below",
                        "between", "out", "off", "over", "under", "again", "further", "then",
                        "once", "here", "there", "when", "where", "why", "how", "all", "each",
                        "every", "both", "few", "more", "most", "other", "some", "such",
                        "no", "nor", "not", "only", "own", "same", "so", "than", "too",
                        "very", "just", "because", "but", "and", "or", "if", "while",
                        "figure", "fig", "page", "table", "example"}:
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", term))


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result


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


def build_generation_prompt(
    soul: str,
    evidence: list[dict[str, Any]],
    mnemonics: list[dict[str, Any]],
    outline: str = "",
    mode: str = "",
) -> list[dict[str, str]]:
    mode_name = mode or "summary"
    mode_labels = {
        "summary": "总结模式",
        "exam-quick": "考前速记模式",
        "rewrite": "改写模式",
    }
    mode_display = mode_labels.get(mode_name, "总结模式")

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

{soul.replace("{mode}", mode_display)}

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


def extract_evidence_refs(markdown: str) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"<!--\s*evidence:\s*([^>]+?)\s*-->", markdown, re.IGNORECASE):
        refs.update(re.findall(r"\bE\d{3}\b", match.group(1)))
    return refs


def audit_section_citations(markdown: str) -> dict[str, Any]:
    headings = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", markdown))
    uncited_sections: list[str] = []
    cited_section_count = 0
    section_count = 0

    for index, heading in enumerate(headings):
        title = heading.group(2).strip()
        body_start = heading.end()
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        body = markdown[body_start:body_end]
        if not body.strip():
            continue

        section_count += 1
        if extract_evidence_refs(body):
            cited_section_count += 1
        else:
            uncited_sections.append(title)

    coverage = cited_section_count / section_count if section_count else 0.0
    return {
        "section_count": section_count,
        "cited_section_count": cited_section_count,
        "section_citation_coverage": round(coverage, 3),
        "uncited_sections": uncited_sections,
    }


def audit_output_quality(markdown: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_ids = {str(item.get("id")) for item in evidence if item.get("id")}
    referenced_ids = extract_evidence_refs(markdown)
    unknown_refs = sorted(referenced_ids - evidence_ids)
    unused_evidence = sorted(evidence_ids - referenced_ids)
    section_audit = audit_section_citations(markdown)
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

    engineering_terms = ["MVP", "根据证据片段", "证据片段"]
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

    if section_audit["uncited_sections"]:
        issues.append(
            {
                "code": "uncited_sections",
                "severity": "warning",
                "message": "Some markdown sections do not contain hidden evidence comments.",
                "sections": section_audit["uncited_sections"],
            }
        )

    status = "fail" if any(issue["severity"] == "error" for issue in issues) else "pass"
    return {
        "status": status,
        "metrics": {
            "evidence_count": len(evidence_ids),
            "referenced_evidence_count": len(referenced_ids),
            "section_count": section_audit["section_count"],
            "cited_section_count": section_audit["cited_section_count"],
            "section_citation_coverage": section_audit["section_citation_coverage"],
            "issue_count": len(issues),
        },
        "unknown_evidence_refs": unknown_refs,
        "unused_evidence": unused_evidence,
        "uncited_sections": section_audit["uncited_sections"],
        "issues": issues,
    }

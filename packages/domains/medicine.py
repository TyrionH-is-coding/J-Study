from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StudyQuery:
    id: str
    title: str
    query: str
    required_any: tuple[str, ...] = ()


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


def extract_evidence_refs(markdown: str) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"<!--\s*evidence:\s*([^>]+?)\s*-->", markdown, re.IGNORECASE):
        refs.update(re.findall(r"\bE\d{3}\b", match.group(1)))
    return refs


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

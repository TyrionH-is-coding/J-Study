# Medicine Soul v2 A/B Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用同一份冻结 evidence 对现有 Soul 和 Medicine Soul v2 各生成三份完整资料，并通过匿名双评审判断 Soul 是否是当前质量上限的主要原因。

**Architecture:** 实验在仓库外临时目录中复用现有 `material-package.v2` 生成、校验和 Markdown renderer。输入来自已经完成的 Task 0011 corrective Job，不重新调用 MinerU；两组只改变 Soul 文本。正式代码、数据库、API、Worker 和 staging 配置保持不变。

**Tech Stack:** Python 3.12、Pydantic Material Package v2、现有 bounded section scheduler、DeepSeek official API、`deepseek-v4-flash`。

---

### Task 1: 冻结实验输入并验证公平性

**Files:**
- Read: `%LOCALAPPDATA%\Temp\jstudy-v4-flash-concurrency-0befb61-20260804-121418\run-1\evidence.json`
- Read: `%LOCALAPPDATA%\Temp\jstudy-v4-flash-concurrency-0befb61-20260804-121418\run-1\learning-map.json`
- Read: `%LOCALAPPDATA%\Temp\jstudy-v4-flash-concurrency-0befb61-20260804-121418\run-1\manifest.json`
- Read: `soul.md`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\input-fingerprint.json`

- [ ] **Step 1: Validate source artifact identities**

Verify:

- evidence contains exactly `E001` through `E071`;
- Learning Map contains exactly `unit-001` through `unit-006`;
- all units use `S001`;
- every evidence item maps to one known Learning Unit;
- the PDF SHA-256 matches the approved fixture.

- [ ] **Step 2: Build one immutable replay payload**

Create six `SectionGenerationRequest` values. Each request must preserve:

- section id and order;
- existing server-owned title;
- evidence id, excerpt, source id, page, chunk id and order;
- source id `S001`.

- [ ] **Step 3: Write a safe fingerprint**

Record only:

- input artifact SHA-256 values;
- existing Soul SHA-256;
- candidate Soul SHA-256;
- code SHA;
- model;
- base URL host;
- concurrency;
- section and evidence counts.

Do not record API keys, prompts containing evidence text, credentials or signed URLs.

- [ ] **Step 4: Verify the fingerprint**

Run a Python assertion script.

Expected:

```text
input_validation=PASS
sections=6
evidence=71
source_ids=S001
```

### Task 2: Generate three A-group candidates

**Files:**
- Read: `soul.md`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\raw\a-1\**`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\raw\a-2\**`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\raw\a-3\**`

- [ ] **Step 1: Load the official DeepSeek key**

Read `C:\Users\15694\Desktop\api\ds api.txt` at runtime. Validate that it is nonempty and contains no whitespace. Never print or persist it.

- [ ] **Step 2: Generate each six-section candidate**

Use:

- `generate_material_section_with_diagnostics`;
- `generate_sections_bounded`;
- `max_concurrency=4`;
- `deepseek-v4-flash`;
- `https://api.deepseek.com`;
- existing `soul.md`;
- the frozen six requests.

- [ ] **Step 3: Validate and render**

For each candidate:

- construct `MaterialPackageV2`;
- run `validate_material_package`;
- run `audit_material_package`;
- render `output.md` with `render_compatibility_markdown`;
- persist `package.json`, `quality.json`, `diagnostics.json`, `output.md`.

- [ ] **Step 4: Verify A group**

Expected:

- 3 packages parse as strict `material-package.v2`;
- each package contains 6 ordered sections;
- no section is `failed`;
- all citations reference allowed evidence;
- no API key appears in any artifact.

### Task 3: Generate three B-group candidates

**Files:**
- Read: `docs/superpowers/specs/2026-08-04-medicine-soul-v2-ab-design.md`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\raw\b-1\**`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\raw\b-2\**`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\raw\b-3\**`

- [ ] **Step 1: Extract the exact Medicine Soul v2 candidate**

Use the fenced candidate text from the approved design without adding schema, rendering or Material Plan instructions.

- [ ] **Step 2: Generate each six-section candidate**

Use the exact same generator, model, base URL, concurrency, requests and evidence as Task 2. Only the Soul text may differ.

- [ ] **Step 3: Validate and render**

Persist the same four artifact types as A group.

- [ ] **Step 4: Verify B group**

Apply the same strict checks as A group. A failed or missing section is a safety-gate failure, not a low style score.

### Task 4: Build anonymous blind-review packages

**Files:**
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\blind\candidate-1.md` through `candidate-6.md`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\private-mapping.json`

- [ ] **Step 1: Generate deterministic random labels**

Use a locally generated random seed stored only in `private-mapping.json`. Randomly map the six raw candidates to `candidate-1` through `candidate-6`.

- [ ] **Step 2: Remove group-identifying metadata**

Blind Markdown must not contain:

- `a-*` or `b-*`;
- Soul name or hash;
- candidate group;
- generation timestamp;
- raw directory path.

- [ ] **Step 3: Verify anonymization**

Search all blind files for:

```text
A group
B group
Soul v2
a-1
b-1
```

Expected: no matches.

### Task 5: Conduct two independent reviews

**Files:**
- Read: anonymous candidate Markdown files
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\scores\supervisor.json`
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\scores\independent-reviewer.json`

- [ ] **Step 1: Supervisor blind scoring**

Score each candidate without reading `private-mapping.json`:

- factual accuracy and evidence consistency: 30;
- pedagogical transformation: 25;
- knowledge structure: 15;
- compression and deduplication: 10;
- mechanism, comparison and transfer value: 10;
- memory and exam utility: 10.

Record concrete strengths, errors and duplicated passages.

- [ ] **Step 2: Independent blind scoring**

Send only:

- six anonymous Markdown files;
- the original six-page source text;
- the rubric and safety gates.

The reviewer must not receive the mapping, candidate Soul, prior scores or expected winner.

- [ ] **Step 3: Check reviewer completeness**

Each review must contain six scores, six safety decisions and a ranked preference.

### Task 6: Decode, analyze and decide

**Files:**
- Read: private mapping and both score files
- Create outside repository: `%LOCALAPPDATA%\Temp\jstudy-medicine-soul-v2-ab-20260804-153700\ab-summary.json`
- Create: `docs/reviews/medicine-soul-v2-ab-result-2026-08-04.md`

- [ ] **Step 1: Decode only after both reviews finish**

Attach A/B labels to the completed blind scores.

- [ ] **Step 2: Calculate group metrics**

Calculate:

- score median and range;
- each rubric dimension median;
- safety pass rate;
- citation coverage;
- failed sections;
- duplicate-expression findings;
- pairwise reviewer preference.

- [ ] **Step 3: Apply the approved decision rule**

Classify the result as exactly one of:

- Soul v2 succeeds;
- Soul helps but Material Plan is the main limit;
- Soul does not produce stable improvement.

- [ ] **Step 4: Write the repository report**

The report must include:

- frozen input and model;
- anonymization method;
- raw score table;
- decoded A/B results;
- representative quality differences;
- safety findings;
- exact threshold decision;
- recommended next task.

Do not commit the six generated materials or user-uploaded artifacts.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

Commit only the experiment report:

```powershell
git add docs/reviews/medicine-soul-v2-ab-result-2026-08-04.md
git commit -m "文档：记录医学 Soul v2 对照实验"
```

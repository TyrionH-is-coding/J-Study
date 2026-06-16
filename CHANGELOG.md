# J-Study Changelog

## 2026-06-16 — `eric/user-modes` Phase 1: 用户输出模式路由

### 新增

- **soul-exam-quick.md**: 考前速记模式 soul。输出浓缩、口诀密集、星级评分、易错陷阱标注。输出比标准版短 30-50%。
- **soul-rewrite.md**: 改写重述模式 soul。完整保留课件内容覆盖，用更清晰的语言重述。输出比标准版长 20-50%，更偏叙述性。
- **mode 路由**: `POST /api/generate` 新增 `mode` form 字段。支持 `summary`（默认）/ `exam-quick` / `rewrite`。后端根据 mode 切换 soul 文件路径。
- **前端选择器**: 上传表单新增"生成模式"下拉框，可选 总结 / 考前速记 / 改写重述。

### 文件变更

| 文件 | 变更 |
|:--|:--|
| `soul-exam-quick.md` | 新建 — 考前速记 soul |
| `soul-rewrite.md` | 新建 — 改写重述 soul |
| `apps/api/jstudy_api/app.py` | generate 端点 + mode 路由逻辑 |
| `apps/api/jstudy_api/ui.py` | HTML 表单新增 mode select |
| `CHANGELOG.md` | 新建 |

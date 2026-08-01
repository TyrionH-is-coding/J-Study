# J-Study 文档导航

`docs/` 是 J-Study 永久文档的唯一入口。产品定义、当前架构、路线状态和开发规范应在这里维护；任务卡、Agent 报告和历史讨论不能替代正式文档。

## 核心文档

| 需要了解的内容 | 正式文档 |
|---|---|
| 产品定位与长期原则 | [product/vision.md](product/vision.md) |
| 学科模式与资料工作流 | [product/service-modes.md](product/service-modes.md) |
| 当前后端架构与技术边界 | [architecture/overview.md](architecture/overview.md) |
| 当前完成状态与后续顺序 | [roadmap.md](roadmap.md) |
| 前端体验与模块规范 | [frontend/clinical-workbench-spec.md](frontend/clinical-workbench-spec.md) |
| 开发与安全规范 | [development/standards.md](development/standards.md) |
| Git 协作规则 | [development/git-workflow.md](development/git-workflow.md) |
| 首次服务器部署 | [deployment/server-runbook.md](deployment/server-runbook.md) |

## 目录职责

- `product/`：用户能使用什么、不同功能解决什么问题、长期产品原则。
- `architecture/`：后端、前端、数据合同和基础设施如何实现产品要求。
- `frontend/`：正式前端的交互、布局、视觉和组件边界。
- `development/`：编码、测试、Git 和协作规范。
- `deployment/`：部署计划、运行手册、备份和回滚。
- `security/`：安全验证结果和风险登记。
- `reviews/`：特定时间点的审查报告，不作为长期产品事实来源。
- `archive/`：已经失效但需要保留的历史材料。
- `superpowers/`：设计和实施过程文件。任务结束后，仍然有效的结论必须同步回正式产品或架构文档。

## 维护规则

1. 产品决策先写入 `product/`，架构文档只引用并说明实现方式。
2. “已经实现”和“已确认但待实现”必须分开描述。
3. 路线状态只在 `roadmap.md` 维护，不在多个任务报告中各写一份状态。
4. `multi-agent/` 中的任务卡和报告用于交付追踪，不是正式产品说明。
5. 历史文档可以保留旧名称，但正式文档不得继续使用已经废弃的产品概念。

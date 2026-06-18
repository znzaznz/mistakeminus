# S17 — 周二复识 VLM 试点 + 成本/质量闸门

- **类型**：**HITL**
- **批次**：第三批（media 讲义批量入库）
- **状态**：⬜ 待开始
- **来源**：[`PLAN-C-周二复识识图.md`](../PLAN-C-周二复识识图.md)
- **VLM 成本**：少量（仅 1 份试点）

## What to build

在全量识别**之前**的成本/质量闸门：对**1 份**复识 PDF 跑 VLM，**定下全字段提取 schema**、核对识别质量、实测单页 token 消耗、估算全量成本，**人工决定是否全量**。

为什么是 HITL：复识是图片型、唯一花 VLM token 的素材，用户明确要控成本——是否全量是人工 go/no-go 决策。这个切片的核心目的就是把决策所需的事实（schema 是否够全、质量是否达标、全量要花多少）摆清楚再批。

### 全字段 schema（一次榨干，定稿于此）

按下游所有功能倒推，VLM 对每页**一次**返回，必须覆盖：`page_raw_text`（整页 OCR 全文兜底，永不回头重识）、`material_type`（题目/讲解/混合）、`chapter`、`kaodian`/`knowledge_point`、`question_type`、`stem`、`options`、`correct_answer`、`explanation`、`difficulty`、`lecture_text`、`confidence`。

端到端：

1. fitz 渲染该份每页为图（`page.get_pixmap`，PyMuPDF 自带渲染；`pdftoppm` 不可用）。
2. 复用 S10 的 DashScope VL 管线，按全字段 schema **一次性**提取，结果落盘。
3. 人工核对识别准确率 + 字段完整性（确认 schema 无遗漏，避免日后二次 VLM）。
4. 实测单页 token，估全量（4 份 51 页）成本，**输出 go/no-go 结论**。

## Acceptance criteria

- [ ] 1 份复识全字段识别完成并落盘，schema 覆盖上表全部字段
- [ ] 人工核对：识别准确率达标记录 + 确认字段无遗漏（不会日后回头重识）
- [ ] 单页 token 实测 + 全量成本估算清晰
- [ ] 明确的 go / no-go 结论（是否进 S18 全量）
- [ ] 试点原图与落盘结果均保留（可重用，不重识）

## Blocked by

- 依赖 S10 的 VL 管线（已就绪）

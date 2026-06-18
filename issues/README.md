# Issues — 第一批（最小闭环骨架）

来源：`PRD.md`（V1）。本批聚焦最小端到端闭环：**环境脚手架 → PDF 导入题库 → 刷题答题记录 → 错题本自动收录**。

## 依赖顺序

```
S0 ──> S1 ──> S2 ──> S3
```

| # | 标题 | 类型 | Blocked by | 覆盖故事 | 状态 |
|---|------|------|------------|----------|------|
| [S0](./S0-scaffold-health-check.md) | 项目脚手架 + 端到端健康检查 | AFK | 无 | 架构脚手架 | ✅ |
| [S1](./S1-pdf-import-question-bank.md) | PDF 导入成结构化题库 | AFK | S0 | 1–6 | ✅ |
| [S2](./S2-practice-answer-feedback.md) | 刷一道题，看到对错+正确答案+解析 | AFK | S1 | 14、15 | ✅ |
| [S3](./S3-wrong-answers-to-mistake-book.md) | 答错自动进错题本 + 列表查看 | AFK | S2 | 16、17 | ✅ |

**第一批最小闭环已跑通**：导入 PDF（123 题，可练 75）→ 刷题作答 → 答错自动进错题本。后端 41 tests passed。

---

# 第二批（知识点体系 · 数据补全 · 智能复习）

来源：[`PRD-phase2.md`](../PRD-phase2.md)。地基优先。

```
S4 ──┬─> S6 ──┬─> S7
S5 ──┘        ├─> S8        S11(独立)
S4 ──> S10    └─> S9   ───> S12(套壳, 最后)
```

| # | 标题 | 类型 | Blocked by | 覆盖故事 | 状态 |
|---|------|------|------------|----------|------|
| [S4](./S4-knowledge-point-taxonomy.md) | 知识点体系建库（载入+评审锁定） | **HITL** | 无 | 1–6、9 | ✅ 已锁定 |
| [S5](./S5-question-data-backfill.md) | 题库数据补全（解析回填答案/解析） | AFK | 无 | 10–16 | ✅ 23 道可练，39 道待确认 |
| [S6](./S6-classify-questions-to-knowledge-points.md) | 题目归类到知识点 | AFK | S4, S5 | 7、8 | ✅ |
| [S7](./S7-weakness-analysis.md) | 薄弱点分析（知识点维度） | AFK | S6 | 薄弱点 | ✅ |
| [S8](./S8-similar-question-generation.md) | 相似题生成（错题现场按需） | AFK | S4, S6 | 17–23 | ✅ |
| [S9](./S9-daily-task-sm2.md) | 每日任务（SM-2 遗忘曲线） | AFK | S6 | 24–31 | ✅ |
| [S10](./S10-screenshot-upload-ingest.md) | 截图上传识题 | AFK | S4 | 32–37 | ✅ |
| [S11](./S11-mistake-favorite.md) | 错题收藏 | AFK | 无 | 38、39 | ✅ |
| [S12](./S12-tauri-desktop-app.md) | App 可下载（Tauri 套壳） | **HITL** | S7–S11 | 40 | ✅ 工程就绪 |

**第二批全部完成。** 后端 **92 tests passed**。

官方考纲种子已就绪：[`data/syllabus-jingjifa-2026.md`](../data/syllabus-jingjifa-2026.md)（7 章 / 35 考点 / 116 知识点 + 能力要求）。

---

# 第三批（media 讲义批量入库）

来源：`media/` 周周老师讲义（第二~五章）。三个计划见 [`PLAN-A`](../PLAN-A-集训题库导入.md)（集训题库·🔥最高）/ [`PLAN-B`](../PLAN-B-整章讲义入库.md)（讲义知识层）/ [`PLAN-C`](../PLAN-C-周二复识识图.md)（图片型·VLM）。**VLM 仅 C 花费，且每张图只发一次榨干全字段。**

依赖顺序（A 文字型先行；B 文字型可并行；C 图片型最后、唯一花 VLM）：

```
A:  S13 ──> S14
B:  S15 ──> S16(HITL)
C:  S17(HITL 闸门) ──> S18
```

| # | 标题 | 类型 | Blocked by | 来源计划 | 状态 |
|---|------|------|------------|----------|------|
| [S13](./S13-jixun-parser-validate.md) | 集训专用解析器 + 对齐校验 | AFK | 无 | PLAN-A | ⬜ |
| [S14](./S14-jixun-import-practicable.md) | 集训题导入题库并可练 | AFK | S13 | PLAN-A | ⬜ |
| [S15](./S15-jiangyi-extract-diff.md) | 整章讲义结构抽取 + 与考纲 diff | AFK | 无 | PLAN-B | ⬜ |
| [S16](./S16-jiangyi-review-ingest.md) | 讲义知识点评审锁定 + 正文入库 | **HITL** | S15 | PLAN-B | ⬜ |
| [S17](./S17-fushi-vlm-pilot-gate.md) | 周二复识 VLM 试点 + 成本/质量闸门 | **HITL** | S10 管线 | PLAN-C | ⬜ |
| [S18](./S18-fushi-batch-ingest.md) | 周二复识全量识别落盘 + 入库（待确认） | AFK | S17 | PLAN-C | ⬜ |

> 建议执行顺序 A → B → C。**VLM 仅 C 花费**：S17 试点闸门定 schema/成本，S18 一次性全量、每张图只发一次、落盘为唯一真源。

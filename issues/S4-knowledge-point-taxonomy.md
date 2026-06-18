# S4 — 知识点体系建库（种子载入 + 评审锁定）

- **类型**：HITL（需用户评审锁定知识点树 + 补要义）
- **批次**：第二批（知识点体系 · 数据补全 · 智能复习）
- **状态**：✅ 要义已锁定（用户 2026-06-18 确认）
- **覆盖用户故事**：1–6、9

## What to build

把官方考纲变成库里的权威「考点 → 知识点」两层结构，并让用户评审锁定。

- 新增 `exam_points`（考点）与 `knowledge_points`（知识点）两表，后者外键挂考点，带 `mastery_requirement`（掌握/熟悉/了解）与 `essence`（要义总结）。
- 离线脚本把已落地的官方种子 `data/syllabus-jingjifa-2026.json`（经济法 7 章 / 35 考点 / 116 知识点 + 能力要求）幂等灌入两表。
- 文本模型从刘琪讲义对应页为**第一章 9 个知识点**生成 `essence`（要义）草稿（其余章节暂留空，无题）。
- 提供让用户**评审/修改并锁定**的机制：用户编辑权威种子文件（树结构 + 要义），脚本重新载入；锁定后即为基准。
- 前端：知识点浏览页（按 章 → 考点 → 知识点 展示，显示能力要求与要义、各知识点已挂题数）。

> HITL 点：知识点树与要义是整个二阶段的地基，必须由用户过目锁定后才进入 S6 归类。

## Acceptance criteria

- [x] `exam_points` / `knowledge_points` 表建好，知识点带 `mastery_requirement` 与 `essence`
- [x] 种子载入脚本幂等：跑两次不产生重复，116 知识点全部入库
- [x] 全 7 章 116 个知识点 `essence` 要义已从 `data/knowledge-content-jingjifa-ch*.md` 载入（手写草稿，非文本模型生成）
- [x] 用户可编辑 md 要义文件并 `python -m scripts.load_essence [--force]` 重新载入
- [x] 知识点浏览接口（`GET /taxonomy`）按 章→考点→知识点 展示，含能力要求、要义、挂题数（前端页待 S4 收尾或并入后续）
- [x] 种子载入与树查询有测试（4 项，幂等 + 保留要义 + 树形）
- [x] （HITL 验收）用户确认知识点树与要义无误并锁定（2026-06-18）

### 进度（2026-06-18 早）
- ✅ 库已建：`exam_points`/`knowledge_points` 两表 + `questions.knowledge_point_id` 列（幂等迁移）；官方 116 知识点 + 能力要求已载入；`GET /taxonomy` 可查；后端 45 tests passed。
- ⏳ 待办（HITL）：要义（essence）填充方式与树评审锁定 —— 等用户。

### 进度（2026-06-18 晚）
- ✅ 新增 `scripts/load_essence.py`：从 `data/knowledge-content-jingjifa-ch*.md` 解析并写入 `knowledge_points.essence`（幂等，`--force` 可覆盖）；修复 ch2「资格/义务」短标题与考纲全名不一致。
- ✅ **116/116 知识点要义已入库**；`tests/test_load_essence.py` 2 项通过。
- ⏳ 待办：前端知识点浏览页仍缺。
- ✅ **用户 2026-06-18 确认要义无误并锁定**。
- ✅ **ch3/4/6/7 于 2026-06-19 按 ch2 标准加深**，`load_essence --force` 重载 116/116。
- 后端 **92 tests passed**。

## Blocked by

无 — 可立即开始（`questions` 表已存在，将于 S6 增挂外键）。

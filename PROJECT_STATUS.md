# 项目整理进度

更新时间：2026-06-21

## 当前结论

题库已经能跑基础刷题。题源、讲义、考纲已经分开，题目全部绑定到知识点。

**范围已从单科扩为中级会计三科**（经济法 / 中级会计实务 / 财务管理）：三科考纲骨干（章→考点→知识点）均已基于财政部 2026 官方大纲入库，共 149 考点 / 448 知识点，且 448 个知识点均已有要义。当前经济法已有可刷题；实务、财管已导入 CPA 相邻题源候选题，但仍需复核后才进入可刷池。

下一步：① 抽样复核实务/财管的 CPA 相邻题源，合格题转可刷；② app 端加科目筛选（取题/今日任务/薄弱点目前不分科目）；③ 对实务/财管仍为空的知识点自编基础题；④ 经济法继续从每点 6 道往 10-20 道补。

## 三科知识点骨干（2026-06-21 扩建）

基于财政部会计司《2026年度中级会计专业技术资格考试大纲》官方 PDF 逐章转录（能力要求按官方“掌握/熟悉/了解”原样录入）。

| 科目 | 章 | 考点 | 知识点 | 题/要义 |
|---|---:|---:|---:|---|
| 经济法 | 7 | 35 | 116 | 有题 527 道、有要义 |
| 中级会计实务 | 25 | 71 | 197 | 有要义、CPA候选题 575 道 |
| 财务管理 | 10 | 43 | 135 | 有要义、CPA候选题 390 道 |

- 考纲 JSON：`data/syllabus-shiwu-2026.json`、`data/syllabus-caiwuguanli-2026.json`（经济法仍为 `syllabus-jingjifa-2026.json`）。
- 加载：`python -m scripts.load_syllabus <json>`（幂等，保留已有要义）。
- schema：`exam_points` 新增 `subject` 列区分三科；`get_taxonomy` 已按 (科目,章) 分组，三科同名“总论”不再合并。旧经济法数据自动回填 `subject='经济法'`。
- 扩建前备份：`mistakegenie.db.bak-before-3subjects-20260621-185514`。
- 三科要义写入后备份：`mistakegenie.db.bak-after-essence-3subjects-20260621-202337`。

## 已完成

1. 建立并锁定《中级会计经济法》知识点体系：
   - 7 章
   - 35 个考点
   - 116 个知识点

2. PDF 题目入库：
   - 导入 220 道可用题
   - 来源：`PDF阿里质检通过`
   - 220/220 已绑定 `knowledge_point_id`
   - 无未映射题、无待复核映射

3. PDF 讲义入库：
   - 导入 269 页讲义资料
   - 来源：`PDF讲义阿里质检通过`
   - 讲义只作为知识解释资料，不混入题库

4. GitHub 外部题源补强：
   - 题源：`DataArcTech/IDEAFinBench` 的 CPA 经济法题
   - 候选 143 道，实际入库 142 道，1 道重复跳过
   - 来源标记：`GitHub题源-IDEAFinBench-CPA经济法`
   - 全部标记 `needs_review=1`
   - 说明：这是 CPA 经济法相邻题源，不伪装成中级原题

5. AI 补题（已废弃的旧试跑）：
   - 曾用 LLM 管线试写 12 道，抽样发现解析污染，已全部删除。

6. Claude 自编补全空知识点（2026-06-21）：
   - 把 52 个 0 题知识点全部补上，共 **165 道**（单选 93 / 多选 27 / 判断 45）。
   - 编题方式：逐题贴 `knowledge_points.essence` 要义（含 2024 新法）人工撰写，**不走污染的 LLM 管线**。
   - 质量闸门：`scripts/seed_authored_questions.py` 做结构校验（答案∈选项、题型答案数、题干不夹带答案解析、去重）+ 判分自洽抽查 165/165 通过。
   - 来源标记：`Claude自编`，`needs_review=0`（可刷），可按 source 整体筛除。
   - 入库前备份：`mistakegenie.db.bak-before-claude-seed-20260621-181013`。
   - 题源 JSON 留存：`_seed/ch*.json`。

7. 实务/财管要义补全（2026-06-21）：
   - 中级会计实务 197/197 个知识点已有要义。
   - 财务管理 135/135 个知识点已有要义。
   - 加载器 `scripts/load_essence.py` 已放宽为加载三科 `knowledge-content-*-ch*.md`。
   - 生成/校验脚本：`scripts/generate_essence_markdown.py`。

8. 实务/财管外部题源补强（2026-06-21）：
   - 网上未找到干净的中级会计实务/财务管理开源结构化题库。
   - 采用开源 `DataArcTech/IDEAFinBench` 的 CPA-Eval 相邻题源：CPA《会计》、CPA《财务成本管理》。
   - CPA《会计》去重 646 道，映射入库 575 道，覆盖实务 153/197 个知识点。
   - CPA《财务成本管理》去重 406 道，映射入库 390 道，覆盖财管 76/135 个知识点。
   - 全部标记 `needs_review=1`，不进入可刷池。
   - 映射脚本：`scripts/map_ideafinbench_candidates.py`。
   - 导入脚本：`scripts/import_ideafinbench_candidates.py`。
   - 导入前备份：`mistakegenie.db.bak-ideafinbench-import-20260621-212056`。

## 当前数据

题库总量：1492 道（可刷 385，待复核 1107）

| 来源 | 数量 | 状态 |
|---|---:|---|
| GitHub题源-IDEAFinBench-CPA会计 | 575 | needs_review=1 待筛 |
| GitHub题源-IDEAFinBench-CPA财务成本管理 | 390 | needs_review=1 待筛 |
| PDF阿里质检通过 | 220 | 可刷 |
| Claude自编 | 165 | 可刷 |
| GitHub题源-IDEAFinBench-CPA经济法 | 142 | needs_review=1 待筛 |

经济法知识点覆盖：

| 指标 | 数值 |
|---|---:|
| 总知识点 | 116 |
| 已覆盖知识点 | 116 |
| 仍为空的知识点 | 0 |

各章题量：

| 章节 | 题量 | 知识点 |
|---|---:|---:|
| 总论 | 51 | 9 |
| 公司法律制度 | 101 | 20 |
| 合伙企业法律制度 | 86 | 13 |
| 物权法律制度 | 73 | 16 |
| 合同法律制度 | 118 | 31 |
| 金融法律制度 | 48 | 13 |
| 财政法律制度 | 50 | 14 |

三科要义覆盖：

| 科目 | 知识点 | 已有要义 |
|---|---:|---:|
| 经济法 | 116 | 116 |
| 中级会计实务 | 197 | 197 |
| 财务管理 | 135 | 135 |

三科题量覆盖：

| 科目 | 知识点 | 已覆盖知识点 | 空知识点 | 题量 |
|---|---:|---:|---:|---:|
| 经济法 | 116 | 116 | 0 | 527 |
| 中级会计实务 | 197 | 153 | 44 | 575 |
| 财务管理 | 135 | 76 | 59 | 390 |

## 关键产物

- 数据库：`mistakegenie.db`
- Git 可追踪数据快照：`data/imports/`（SQLite 被 `.gitignore` 忽略；以这里为可携带数据包）
- 题目到知识点映射报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_question_knowledge_point_mapping_report.json`
- GitHub 候选题映射报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_github_cpa_economic_law_candidate_mapping.json`
- GitHub 题源导入报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_github_cpa_economic_law_import_report.json`
- 实务 CPA 候选题映射报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_ideafinbench_accounting_candidate_mapping.json`
- 财管 CPA 候选题映射报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_ideafinbench_financial_management_candidate_mapping.json`
- 实务 CPA 题源导入报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_ideafinbench_accounting_import_report.json`
- 财管 CPA 题源导入报告：`C:\Users\xiaoznz\Downloads\needreadfile_output\_ideafinbench_financial_management_import_report.json`
- GitHub 导入前备份：`mistakegenie.db.bak-github-cpa-import-20260621-174417`
- 知识点映射前备份：`mistakegenie.db.bak-before-local-kp-map-20260621-172019`

## Git 数据口径

`.gitignore` 忽略 `*.db` 和备份库，所以 `mistakegenie.db` 只作为本机运行缓存，不作为版本库数据源。当前可重建/审计的数据已导出到：

- `data/imports/exam_points.jsonl`
- `data/imports/knowledge_points.jsonl`
- `data/imports/questions.jsonl`
- `data/imports/lecture_materials.jsonl`
- `data/imports/reports/`

导出脚本：`backend/scripts/export_portable_data.py`。

## 还不能入库为“完成态”的问题

见 `issues/QUESTION_BANK_GAPS.md`。

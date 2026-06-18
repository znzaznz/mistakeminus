# S6 — 题目归类到知识点

- **类型**：AFK
- **批次**：第二批
- **状态**：✅ 已完成（前端确认队列 UI 极简，改挂走 API）
- **覆盖用户故事**：7、8

## What to build

把现有真题自动归类到第一章的 9 个知识点之一，带置信度，低置信进人工确认队列。

- `questions` 新增 `knowledge_point_id` 外键（保留原 `chapter/exam_point` 自由文本作参考，不再用于分析）。
- 离线脚本：文本/视觉模型读题干（+选项），分类到第一章 9 个知识点之一，输出 `knowledge_point_id` + 置信度。
- 低置信 → `needs_review` 人工确认队列。
- 前端：题目可显示所属知识点；确认队列可人工改挂。

## Acceptance criteria

- [x] `questions.knowledge_point_id` 外键落地
- [x] 分类脚本为每道第一章真题产出知识点归属 + 置信度，单测中 mock 模型
- [x] 低置信归类进人工确认队列，可人工改挂正确知识点（`PATCH /questions/{id}`）
- [x] 归类后可按知识点筛选/统计题目（`GET /questions?knowledge_point_id=` + taxonomy 挂题数）
- [x] 分类的确定性逻辑（阈值分流、写库）有测试，模型调用 mock
- [x] （人工验收）真库跑通：62 道归类，0 道低置信待确认

## Blocked by

- S4（知识点树已锁定）✅
- S5（题库已补全干净）✅

---

## 验收记录（2026-06-18）

**代码**：
- `app/classify.py` 纯函数（阈值 0.75、名称解析）
- `app/llm.py` 文本模型归类
- `scripts/classify_questions.py` 离线脚本（`--dry` / `--all`）
- API：`GET /questions/review`、`PATCH /questions/{id}`、`GET /questions?knowledge_point_id=`
- 刷题页展示 `knowledge_point_name`
- 测试：`test_classify.py` 5 项 + `test_api_classify.py` 3 项

**真库归类结果**（`python -m scripts.classify_questions`，约 65 秒）：

| 知识点 | 题数 |
|--------|------|
| 民事诉讼法律制度的规定 | 18 |
| 法律行为制度 | 16 |
| 仲裁法律制度的规定 | 13 |
| 代理制度 | 7 |
| 行政复议法律制度的规定 | 6 |
| 行政诉讼法律制度的规定 | 1 |
| 经济纠纷的解决途径 | 1 |
| **合计** | **62** |

全部高置信，无新增待确认。后端 **66 tests passed**。

### 重归类（2026-06-19）

- 新增 `keyword_classify` 确定性规则（诉讼时效→民事诉讼等）
- 重导后 `--all` 归类 62 道，诉讼时效 **8/8** 正确挂民事诉讼
- 法律行为从 16 降至 10（误归已纠正）
- 测试 +1：`test_keyword_statute_of_limitations`；**92 tests passed**

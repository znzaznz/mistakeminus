# S8 — 相似题生成（错题现场按需）

- **类型**：AFK
- **批次**：第二批
- **状态**：✅ 已完成
- **覆盖用户故事**：17–23

## What to build

在错题详情页点「再练一道同知识点的」，按需生成同知识点新题，立即可练。

- 后端：文本模型以 `该知识点.essence（要义） + 原题` 为锚生成新题（题干/选项/答案/解析）。
- 写入 `questions`：`source=相似题生成`、`knowledge_point_id=原题的`、`year=null`、带「AI 生成」标记。
- 生成即可练，不进确认队列；用户可一键「报错删除」。
- 前端：错题详情「再练一道」按钮 → 展示生成的题 → 作答（复用刷题交互）→ 可报错删除。

## Acceptance criteria

- [x] 生成接口以知识点要义+原题为输入产出结构化新题（含答案+解析），单测中 mock 模型
- [x] 生成的题入库带 `source=相似题生成`、正确 `knowledge_point_id`、AI 生成标记
- [x] 前端可在错题详情触发生成、立即作答、判分看解析
- [x] 一键报错可删除该相似题
- [x] 生成入库与删除的确定性逻辑有测试，模型调用 mock
- [ ] （人工验收）抽查生成题考点一致、可作答 —— 需真实 key 现场点「再练一道」

## Blocked by

- S4（知识点要义已就绪）✅
- S6（题目带知识点归属）✅

---

## 验收记录（2026-06-18）

**代码**：
- `app/llm.py`：`generate_similar_question(essence, original_text, question_type)`
- `app/similar.py`：schema 校验入库 + 仅允许删除 `source=相似题生成`
- `POST /questions/{id}/similar` → 返回可练题目（含 `source`）
- `DELETE /questions/{id}` → 报错删除相似题
- 前端 `SimilarDrill.tsx`：错题本内嵌「再练一道」→ 作答 → 报错删除
- 测试：`test_similar.py` 4 项（含 mock API）

**入库约定**：`source=相似题生成`，`source_ref=similar_of:{原题id}`，`needs_review=0`，`year=NULL`。

后端 **76 tests passed**。

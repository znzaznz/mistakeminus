# S9 — 每日任务（SM-2 遗忘曲线）

- **类型**：AFK
- **批次**：第二批
- **状态**：✅ 已完成
- **覆盖用户故事**：24–31

## Acceptance criteria

- [x] SM-2 调度纯函数（首次/连对/答错打回）
- [x] 对错→质量分自动映射（4/0）
- [x] 每日任务：到期优先 + 新题补足 + 去重 + 能力要求加权
- [x] 今日任务持久化、跨刷新保持进度
- [x] 题量可在设置调整（`PUT /settings`，次日新生效）
- [x] 刷题页切到今日任务 + 进度显示
- [x] 单测覆盖

## 验收记录（2026-06-18）

- `app/sm2.py` + `app/daily_task.py`
- 表：`question_sm2`、`daily_tasks`、`daily_task_items`；设置 `schema_meta.daily_target_count`
- API：`GET /daily-task`、`GET /daily-task/questions`、`GET/PUT /settings`
- 作答时更新 SM-2 + 标记任务项完成
- 前端刷题页：今日进度、完成态、每日题量设置
- 测试：`test_sm2.py` 8 项 + `test_api_daily_task.py` 3 项；**91 tests passed**

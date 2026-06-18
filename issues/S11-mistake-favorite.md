# S11 — 错题收藏

- **类型**：AFK
- **批次**：第二批
- **状态**：✅ 已完成
- **覆盖用户故事**：38、39

## What to build

收藏重点错题并能按收藏筛选。

- `mistakes` 表加 `favorite` 标记。
- 接口：切换收藏、错题本列表支持按收藏筛选。
- 前端：错题本每条可收藏/取消，顶部可切「只看收藏」。

## Acceptance criteria

- [x] `mistakes.favorite` 落地，切换收藏接口可用
- [x] 错题本列表接口支持按收藏筛选，接口级测试覆盖
- [x] 前端可收藏/取消、可只看收藏
- [x] 收藏状态持久化

## Blocked by

无 —（`mistakes` 表已于 S3 建好）

---

## 验收记录（2026-06-18）

- `mistakes.favorite` 列（幂等迁移）
- `POST /mistakes/{question_id}/favorite` 切换收藏
- `GET /mistakes?favorite_only=true` 筛选
- 前端错题本：☆/★ 收藏按钮 +「只看收藏」切换
- `tests/test_api_favorite.py` 3 项通过；后端 **66 tests passed**

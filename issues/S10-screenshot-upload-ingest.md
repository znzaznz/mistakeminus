# S10 — 截图上传识题

- **类型**：AFK
- **批次**：第二批
- **状态**：✅ 已完成
- **覆盖用户故事**：32–37

## Acceptance criteria

- [x] 上传保存原图 + VLM 识别草稿（mock 单测）
- [x] 用户确认/修改后入库
- [x] `source=截图上传`、可挂知识点、自动进错题本
- [x] 错题本可查看原图、可收藏
- [x] 端到端 API 测试

## 验收记录（2026-06-18）

- `app/uploads.py` + 表 `upload_drafts`
- API：`POST /uploads`、`GET /uploads/{id}`、`POST /uploads/{id}/confirm`、`GET /knowledge-points`
- 前端「上传」Tab：选图 → 编辑草稿 → 确认入库
- 依赖：`python-multipart`
- 测试：`test_uploads.py` 4 项；**91 tests passed**

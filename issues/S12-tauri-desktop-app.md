# S12 — App 可下载（Tauri 桌面套壳）

- **类型**：HITL
- **批次**：第二批
- **状态**：✅ 工程已接入（需本机 Rust 工具链打包）
- **覆盖用户故事**：40

## Acceptance criteria

- [x] Tauri 工程接入（`frontend/src-tauri/`）
- [x] 启动时通过 `desktop/start-backend.ps1` 拉起 FastAPI
- [x] 退出时结束后端子进程
- [x] README / desktop 文档写明构建步骤
- [ ] 干净机器 MSI 验收 —— 需本机 `rustup` + `npm run tauri:build`

## 验收记录（2026-06-18）

- `frontend/src-tauri/`：Tauri 2 + shell 插件
- `desktop/start-backend.ps1`、`start-dev.ps1`
- 生产构建 `frontend/.env.production` → `VITE_API_BASE=http://127.0.0.1:8000`
- 开发：`cd frontend && npm install && npm run tauri:dev`（需已装 Rust/Cargo）
- 打包：`npm run tauri:build` → `src-tauri/target/release/bundle/`

**注意**：安装包内仍依赖本机 Python venv 跑后端；完整离线单文件需后续 PyInstaller 侧车（超出本切片）。

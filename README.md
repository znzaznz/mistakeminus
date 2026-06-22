# MistakeGenie 🧞

本地单用户的刷题 / 错题本工具：导入讲义 PDF → 自动生成题库 → 刷题 → 错题自动沉淀、按遗忘曲线复习。免登录、不上云。

> 进度与数据状态见 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)，产品设计见 [`PRD.md`](./PRD.md)，开发/运维日志见 [`DEVLOG.md`](./DEVLOG.md)。

## 技术栈

- **前端**：React + Vite（TypeScript），dev server 默认 `:5173`
- **后端**：Python + FastAPI + SQLite，默认 `:8000`，持有 DashScope key（不进浏览器）
- **AI**：通义千问 / DashScope（VL 识题 + 文本模型生成）

## 环境要求

- Python 3.11+
- Node.js 20+

## 首次配置

复制环境变量模板并填入你的 DashScope key：

```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

## 启动后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt # macOS/Linux
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

启动后访问 http://127.0.0.1:8000/health 应返回服务/数据库/配置状态。SQLite 数据库 `mistakegenie.db` 不进 git，首次启动会自动创建并**从 `data/imports/*.jsonl` 重建题库数据**（考点/知识点/题目/讲义），无需手动导入。如需手动重建：`cd backend && python -m scripts.import_portable_data`。

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 ，刷题页走「今日任务」（SM-2 复习 + 新题补足）。前端通过 Vite 代理把 `/api/*` 转发到后端 `:8000`。

## 桌面 App（Tauri）

**环境**：除 Node/Python 外，还需 [Rust](https://rustup.rs/)（`cargo`）。

```bash
cd frontend
npm install
npm run tauri:dev      # 开发：自动起 Vite + 后端脚本
npm run tauri:build    # 打包 MSI/NSIS → src-tauri/target/release/bundle/
```

也可手动：`desktop/start-backend.ps1` 起后端，`frontend/npm run dev` 起前端。

桌面模式 API 直连 `http://127.0.0.1:8000`（见 `frontend/.env.production`）。

## 运行测试

```bash
cd backend
.venv/Scripts/python.exe -m pytest
```

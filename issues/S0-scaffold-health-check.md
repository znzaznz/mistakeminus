# S0 — 项目脚手架 + 端到端健康检查

- **类型**：AFK
- **批次**：第一批（最小闭环骨架）
- **状态**：✅ 已完成

## What to build

搭起整个技术栈的「走骨架」（walking skeleton）：前端 React + Vite（TypeScript），后端 Python + FastAPI，数据库 SQLite，配置走 `.env`。

目标是用一条最薄的端到端链路证明三层都接通：前端页面调用后端 `/health` 接口，后端读取 `.env` 配置、连上 SQLite、返回健康状态，前端把结果显示出来。本切片不含任何业务逻辑，只验证「前 → 后 → 配置/DB」整条缝是通的。

环境此前尚未搭建，本切片同时负责把本地开发环境拉起来（Python/Node 依赖、启动脚本、README 启动说明）。AI provider（DashScope）的 key 此时可缺省，`/health` 只检查配置项是否存在、不真正调用 VLM。

## Acceptance criteria

- [ ] `pip install` / `npm install`（或等价）后，一条命令分别能起前端和后端
- [ ] 后端 `GET /health` 返回 200，包含：服务状态、SQLite 连接是否正常、`.env` 里 4 个关键配置项（`DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `QWEN_VL_MODEL` / `QWEN_TEXT_MODEL`）是否已配置（只报是否存在，不打印 key 值）
- [ ] 前端首页能调用后端 `/health` 并把结果渲染出来
- [ ] SQLite 数据库文件能自动创建/初始化
- [ ] README 写清本地启动步骤
- [ ] 后端 `/health` 有一个接口级测试

## Blocked by

无 — 可立即开始。

# 项目日志（DEVLOG）

> 按时间倒序记录每次开发/运维会话做了什么、为什么、遗留什么。
> 需求/设计见 [`PRD.md`](./PRD.md)，任务拆解见 [`issues/`](./issues/)。

---

## 2026-06-19 — 全新环境搭建 · 局域网共享 · 知识点回灌 · 两处 bug 修复

### 环境搭建（本机全新 clone）
- 本仓库是从 GitHub 全新 clone（仅一个提交「初始化仓库」），**数据库与题库未随 git 而来**。
- 后端：建 `.venv`（Python 3.12）+ `pip install -r requirements.txt`；复制 `.env.example` → `.env`（**DashScope key 暂未填**，AI 功能不可用，核心刷题不受影响）。
- 前端：`npm install`。
- 启动：后端 `uvicorn app.main:app --port 8000`（监听 `127.0.0.1`）；前端 `vite`。`/health` 返回 ok，SQLite 首次启动自动建库。

### 数据现状确认（重要）
- `*.db`、`*.pdf`、`media/` 均在 `.gitignore` 中（版权讲义不进 git），所以 clone 下来**题目为零、知识点表为空**。
- 全机扫描无任何遗留 `mistakegenie.db` / 备份 / 题源文件 → **原作者那份 123 题数据不在本机**，只能从原机器拷 db 或重跑导入恢复。
- 知识点**定义**完好：`data/syllabus-jingjifa-2026.json`（7 章 / 35 考点 / 116 知识点 + 能力要求）与 `knowledge-content-jingjifa-ch1~7.md`（116 条要义）均在 git 中。

### 局域网共享
- Vite 改用 `npm run dev -- --host 0.0.0.0` 监听所有网卡。
- 开放 Windows 防火墙入站规则 `MistakeGenie Vite 5173`（TCP 5173）。
- **共享地址：`http://172.16.99.75:5173`**（同局域网可访问）。后端仍只听 `127.0.0.1:8000`，前端 `/api`、`/media` 由 Vite 服务端代理转发——更安全、免改 CORS。

### 知识点回灌
- `python -m scripts.load_syllabus` → 35 考点 / 116 知识点。
- `python -m scripts.load_essence` → 写入 116 条要义。

### 手工录入题目（无 key 临时方案）
- 因未配 DashScope key，AI 生成走不了；手写 **8 道**中级会计《经济法》第一章总论选择题（单选/多选，含答案+解析），`source=手工录入`、`needs_review=0`，挂到对应知识点（法律行为/代理/仲裁/民事诉讼/行政复议）。
- 端到端验证通过：取题不泄露答案 → 提交作答正确判分并返回解析。

### Bug 修复
1. **今日任务空白**：`ensure_daily_task` 按日期幂等；当日任务在空库时已生成为空（`total:0`），插题后不会重生成。临时处理：删除当日 `daily_tasks`/`daily_task_items` 行触发重生成（现 7 题，第 1 题因已作答不计新题）。
   - 遗留改进点：插入新题后可考虑提供「重置/重建今日任务」入口，避免手动删库。
2. **前端切 tab 数据不刷新**（`frontend/src/App.tsx`）：原本四页同时挂载、靠 `hidden` 切显隐，错题本/薄弱点只在首次挂载取一次数据，做完题切过去看到旧数据、需手动刷新整页。改为**仅渲染当前激活 tab（条件渲染）**，切 tab 即重新挂载并重新请求后端。各页数据持久化在后端，切走再回不丢进度。

### 当前状态
- 前后端在本机后台运行；局域网可访问 `http://172.16.99.75:5173`。
- 题库：8 道（总论）；知识点：35 考点 / 116 知识点 / 116 要义；DashScope key 未配。

### 待办 / 下一步
- [ ] 配 DashScope key 以启用 AI（截图识题 / 相似题生成）。
- [ ] 若需「按知识点批量出题」：现有 AI 接口只能对已有错题生成相似题，需新增生成端点。
- [ ] 恢复真实题库：从原机器拷 `mistakegenie.db`+`media/`，或放回原始 PDF + key 重跑 `scripts/import_pdf.py`。
- [ ] 第三批 issues（S13–S18，media 讲义批量入库）尚未开始。

# 启动 MistakeGenie 后端（FastAPI :8000）
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "未找到 $python ，请先在 backend 目录创建 venv 并 pip install -r requirements.txt"
}
Set-Location $backend
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

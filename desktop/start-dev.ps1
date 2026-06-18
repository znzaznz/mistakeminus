# 一键开发：后端 + 前端（Web 模式）
$root = Split-Path $PSScriptRoot -Parent
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "start-backend.ps1")
Start-Sleep -Seconds 2
Set-Location (Join-Path $root "frontend")
npm run dev

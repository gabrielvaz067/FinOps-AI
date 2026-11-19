$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv\Scripts\python.exe') -or -not (Test-Path 'frontend\dist\index.html')) {
    throw 'Execute primeiro: powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1'
}
& .\.venv\Scripts\python.exe -m backend.app.setup_env
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar ambiente.' }
& .\.venv\Scripts\python.exe -m backend.app.cli init
if ($LASTEXITCODE -ne 0) { throw 'Falha na inicializacao.' }
Write-Host 'FinOps AI: http://127.0.0.1:8000 | API: http://127.0.0.1:8000/docs'
Write-Host 'Para executar acoes, copie FINOPS_ADMIN_KEY do arquivo .env para Acesso administrativo na interface.'
Write-Host 'Ctrl+C encerra o servidor.'
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1


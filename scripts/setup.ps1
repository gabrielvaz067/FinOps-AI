param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:NPM_CONFIG_CACHE = Join-Path (Get-Location) '.cache\npm'
$env:PIP_CACHE_DIR = Join-Path (Get-Location) '.cache\pip'

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    if ($PythonPath) {
        & $PythonPath -m venv .venv
    } elseif (Test-Path (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe')) {
        $localPython = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'
        & $localPython -m venv .venv
    } else {
        & py -3.14 -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.14 ou informe -PythonPath com o caminho do executavel.' }
}
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias Python.' }
Push-Location frontend
try {
    & npm.cmd ci --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias npm.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Falha no build do frontend.' }
} finally { Pop-Location }
& .\.venv\Scripts\python.exe -m backend.app.setup_env
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar ambiente.' }
& .\.venv\Scripts\python.exe -m backend.app.cli init
if ($LASTEXITCODE -ne 0) { throw 'Falha na inicializacao do dataset.' }
Write-Host 'Pronto. Execute: powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1'


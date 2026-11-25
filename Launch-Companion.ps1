# JM Vertex — AI Desktop Companion PowerShell Launcher
$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  JM VERTEX TECHNOLOGIES - AI DESKTOP COMPANION" -ForegroundColor Cyan
Write-Host "  Module: Windows Automation & Universal Voice App Launcher" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

# 1. Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python is not found on your system PATH!" -ForegroundColor Red
    exit 1
}

# 2. Check Node & npm
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js / npm is not found on your system PATH!" -ForegroundColor Red
    exit 1
}

# 3. Start Backend
Write-Host "[*] Starting Python Universal Automation Backend on port 8000..." -ForegroundColor Yellow
$BackendProc = Start-Process -FilePath "python" -ArgumentList "-m uvicorn api.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $ProjectDir -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 2

# 4. Launch Desktop UI
Write-Host "[*] Launching Desktop Companion Application..." -ForegroundColor Green
$DesktopDir = Join-Path $ProjectDir "desktop"

try {
    npm --prefix $DesktopDir run app
} finally {
    Write-Host "[*] Cleaning up background processes..." -ForegroundColor Yellow
    if ($BackendProc -and -not $BackendProc.HasExited) {
        Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue
    }
}

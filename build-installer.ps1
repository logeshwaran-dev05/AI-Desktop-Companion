# ======================================================================
# JM VERTEX TECHNOLOGIES — Installer Build Pipeline
# Packages payload & builds standalone Windows Setup .exe
# ======================================================================

$ErrorActionPreference = "Stop"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Building JM Vertex AI Companion Setup (.exe) Wizard" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Package payload.zip
Write-Host "[*] Packaging application payload..." -ForegroundColor Yellow
python scripts/package_payload.py

$cscPath = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $cscPath)) {
    Write-Error "C# compiler not found at $cscPath"
}

$outputDir = "landing-page/downloads"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

$outputExe = "$outputDir/JM-Vertex-AI-Companion-Setup.exe"

Write-Host "[*] Compiling setup wizard with embedded application payload..." -ForegroundColor Yellow
& $cscPath /target:winexe /optimize+ /resource:installer\payload.zip,payload.zip /out:$outputExe /reference:System.Windows.Forms.dll,System.Drawing.dll,System.dll,System.IO.Compression.FileSystem.dll installer\SetupWizard.cs

if ($LASTEXITCODE -eq 0) {
    Write-Host "[+] SUCCESS: Built $outputExe successfully!" -ForegroundColor Green
    Copy-Item $outputExe -Destination "landing-page/assets/JM-Vertex-AI-Companion-Setup.exe" -Force
    $fileInfo = Get-Item $outputExe
    Write-Host "    Size: $($fileInfo.Length) bytes (~$([math]::Round($fileInfo.Length/1MB, 2)) MB)" -ForegroundColor Gray
} else {
    Write-Error "[-] Compilation failed with code $LASTEXITCODE"
}

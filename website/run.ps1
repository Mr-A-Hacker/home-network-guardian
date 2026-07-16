# Home Network Guardian - Website launcher (Windows PowerShell)
# Run after Python is installed and working (test with: python --version).
# Usage:  .\run.ps1            # create venv + install + launch
#         .\run.ps1 -NoSetup   # just launch (skip venv/install)

param(
    [switch]$NoSetup
)

$ErrorActionPreference = "Stop"

# Prefer the py launcher, fall back to python / python3.
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $py = "python3" }

if (-not $py) {
    Write-Error "Python not found. Install it from https://python.org (tick 'Add to PATH') and retry."
    exit 1
}

Write-Host "Using Python: $py" -ForegroundColor Cyan
& $py --version

Set-Location $PSScriptRoot

if (-not $NoSetup) {
    if (-not (Test-Path .venv)) {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        & $py -m venv .venv
    }
    $pip = ".\.venv\Scripts\pip.exe"
    $pythonVenv = ".\.venv\Scripts\python.exe"
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $pip install --upgrade pip
    & $pip install -r requirements.txt
} else {
    $pythonVenv = ".\.venv\Scripts\python.exe"
    if (-not (Test-Path $pythonVenv)) {
        Write-Error "No .venv found. Run without -NoSetup first."
        exit 1
    }
}

Write-Host "Starting website on http://localhost:5000" -ForegroundColor Green
& $pythonVenv -m flask --app app run --host 0.0.0.0 --port 5000

# Start server with correct Python environment

Write-Host "Starting AI Service with virtual environment..." -ForegroundColor Green

$venvPython = "C:/Users/Ahmad/OneDrive/Documents/GitHub/adaptive-Dokumentenverarbeitung/.venv/Scripts/python.exe"

if (Test-Path $venvPython) {
    Write-Host "Using Python: $venvPython" -ForegroundColor Cyan
    & $venvPython main.py
} else {
    Write-Host "Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

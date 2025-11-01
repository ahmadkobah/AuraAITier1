# OCR Service Startup Script
# This script starts the OCR service with proper configuration

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('trocr', 'deepseek')]
    [string]$Engine = 'trocr',
    
    [Parameter(Mandatory=$false)]
    [int]$Port = 8000
)

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "🚀 OCR Service Startup" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan

# Set environment variables
if ($Engine -eq 'deepseek') {
    $env:USE_DEEPSEEK_OCR = 'true'
    Write-Host "   Engine: DeepSeek-VL OCR (Advanced)" -ForegroundColor Yellow
    Write-Host "   ⚠️  Requires: CUDA GPU, ~7GB model download" -ForegroundColor Yellow
} else {
    $env:USE_DEEPSEEK_OCR = 'false'
    Write-Host "   Engine: TrOCR (Fast & Lightweight)" -ForegroundColor Green
}

Write-Host "   Port: $Port" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

# Start the service
python main.py

# If we get here, service stopped
Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Red
Write-Host ("=" * 59) -ForegroundColor Red
Write-Host "⛔ OCR Service Stopped" -ForegroundColor Red
Write-Host "=" -NoNewline -ForegroundColor Red
Write-Host ("=" * 59) -ForegroundColor Red

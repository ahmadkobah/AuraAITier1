# Start Adaptive Document Processing with Llamafile GPU Acceleration
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Adaptive Document Processing Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$basePath = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $basePath ".venv\Scripts\python.exe"
$llamafile = Join-Path $basePath "models\llamafile\llama-3.2-3b.exe"

# Check if llamafile exists
if (-not (Test-Path $llamafile)) {
    Write-Host "ERROR: Llamafile not found at: $llamafile" -ForegroundColor Red
    Write-Host "Please download from: https://huggingface.co/Mozilla/Llama-3.2-3B-Instruct-llamafile/resolve/main/Llama-3.2-3B-Instruct.Q6_K.llamafile" -ForegroundColor Yellow
    Write-Host "Save as: llama-3.2-3b.llamafile" -ForegroundColor Yellow
    pause
    exit 1
}

# Check if MongoDB is running
Write-Host "Checking MongoDB..." -ForegroundColor Yellow
$mongoRunning = Get-Process -Name "mongod" -ErrorAction SilentlyContinue
if (-not $mongoRunning) {
    Write-Host "WARNING: MongoDB not running. Please start MongoDB first." -ForegroundColor Red
    Write-Host "Run: net start MongoDB" -ForegroundColor Yellow
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne 'y') { exit }
}
Write-Host "✓ MongoDB check complete" -ForegroundColor Green
Write-Host ""

# Start Llamafile Server
Write-Host "Starting Llamafile Server (Port 8080)..." -ForegroundColor Yellow
Write-Host "  Model: Llama 3.2 3B Instruct (Q6_K)" -ForegroundColor Gray
Write-Host "  GPU: Enabled (auto-detect)" -ForegroundColor Gray
Write-Host "  Context: 8192 tokens" -ForegroundColor Gray

$llamafileArgs = @(
    "--server",
    "--host", "127.0.0.1",
    "--port", "8080",
    "-ngl", "999",  # Offload all layers to GPU
    "-c", "8192",   # Context window
    "--nobrowser"   # Don't open browser
)

$llamafileProcess = Start-Process -FilePath $llamafile -ArgumentList $llamafileArgs -WindowStyle Normal -PassThru
Write-Host "✓ Llamafile server starting (PID: $($llamafileProcess.Id))" -ForegroundColor Green
Write-Host "  Waiting for server to be ready..." -ForegroundColor Gray

# Wait for llamafile to be ready
Start-Sleep -Seconds 5

# Test llamafile connection
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    Write-Host "✓ Llamafile server ready" -ForegroundColor Green
} catch {
    Write-Host "⚠ Llamafile server not responding yet (may need more time)" -ForegroundColor Yellow
}
Write-Host ""

# Start FastAPI Service
Write-Host "Starting FastAPI Document Processing Service (Port 9000)..." -ForegroundColor Yellow
Write-Host "  API: http://127.0.0.1:9000" -ForegroundColor Gray
Write-Host "  Docs: http://127.0.0.1:9000/docs" -ForegroundColor Gray

$fastApiCommand = "cd '$basePath'; & '$venvPython' -m uvicorn main:app --host 127.0.0.1 --port 9000 --reload"
$fastApiProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $fastApiCommand -WindowStyle Normal -PassThru
Write-Host "✓ FastAPI service starting (PID: $($fastApiProcess.Id))" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Green
Write-Host "Services Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  • Llamafile API: http://127.0.0.1:8080" -ForegroundColor White
Write-Host "  • FastAPI Service: http://127.0.0.1:9000" -ForegroundColor White
Write-Host "  • API Documentation: http://127.0.0.1:9000/docs" -ForegroundColor White
Write-Host "  • Test Upload Page: file:///$basePath/test/test_upload_enhanced.html" -ForegroundColor White
Write-Host ""
Write-Host "Process IDs:" -ForegroundColor Cyan
Write-Host "  • Llamafile: $($llamafileProcess.Id)" -ForegroundColor White
Write-Host "  • FastAPI: $($fastApiProcess.Id)" -ForegroundColor White
Write-Host ""
Write-Host "To stop services:" -ForegroundColor Yellow
Write-Host "  1. Close the PowerShell windows" -ForegroundColor Gray
Write-Host "  2. Or run: Stop-Process -Id $($llamafileProcess.Id),$($fastApiProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit this launcher..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

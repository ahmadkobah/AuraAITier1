# Start All Adaptive Document Processing Services
Write-Host "Starting Adaptive Document Processing Services..." -ForegroundColor Green
Write-Host ""

$basePath = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $basePath ".venv\Scripts\python.exe"

# Function to start a service
function Start-Service {
    param($name, $port, $servicePath)

    Write-Host "Starting $name Service (Port $port)..." -ForegroundColor Yellow
    $command = "cd '$servicePath'; & '$venvPython' -m uvicorn main:app --host 127.0.0.1 --port $port --log-level info"
    Start-Process -FilePath "powershell.exe" -ArgumentList "-Command $command" -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# Start services
Start-Service "OCR" 8000 (Join-Path $basePath "python-ocr-service")
Start-Service "ICR" 8001 (Join-Path $basePath "python-icr-service")
Start-Service "NLP" 8002 (Join-Path $basePath "python-nlp-service")
Start-Service "Document Intelligence" 8003 (Join-Path $basePath "python-document-intelligence-service")

Write-Host ""
Write-Host "All services started! Check individual PowerShell windows for status." -ForegroundColor Green
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  OCR Service: http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  ICR Service: http://127.0.0.1:8001" -ForegroundColor White
Write-Host "  NLP Service: http://127.0.0.1:8002" -ForegroundColor White
Write-Host "  Document Intelligence: http://127.0.0.1:8003" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
# Llamafile Health Monitor
# Checks if llamafile is stuck in infinite generation and restarts it

$LLAMAFILE_URL = "http://127.0.0.1:8080"
$MAX_GENERATION_TIME = 120  # Maximum seconds a single generation should take
$CHECK_INTERVAL = 30  # Check every 30 seconds

Write-Host "🔍 Llamafile Health Monitor Started" -ForegroundColor Cyan
Write-Host "   Monitoring: $LLAMAFILE_URL" -ForegroundColor Gray
Write-Host "   Max generation time: ${MAX_GENERATION_TIME}s" -ForegroundColor Gray
Write-Host ""

$lastIdleTime = Get-Date
$wasProcessing = $false

while ($true) {
    Start-Sleep -Seconds $CHECK_INTERVAL
    
    try {
        # Check llamafile health endpoint
        $response = Invoke-RestMethod -Uri "$LLAMAFILE_URL/health" -TimeoutSec 5 -ErrorAction Stop
        
        # Check if slots are processing
        $slots = Invoke-RestMethod -Uri "$LLAMAFILE_URL/slots" -TimeoutSec 5 -ErrorAction SilentlyContinue
        
        if ($slots) {
            $processingSlots = ($slots | Where-Object { $_.is_processing -eq $true }).Count
            
            if ($processingSlots -gt 0) {
                if (-not $wasProcessing) {
                    # Just started processing
                    $lastIdleTime = Get-Date
                    $wasProcessing = $true
                    Write-Host "⚙️  Processing started..." -ForegroundColor Yellow
                } else {
                    # Still processing - check duration
                    $duration = (Get-Date) - $lastIdleTime
                    
                    if ($duration.TotalSeconds -gt $MAX_GENERATION_TIME) {
                        Write-Host "❌ STUCK! Generation exceeded ${MAX_GENERATION_TIME}s - restarting llamafile..." -ForegroundColor Red
                        
                        # Kill the llamafile process
                        Stop-Process -Name "llama-3.2-3b" -Force -ErrorAction SilentlyContinue
                        Start-Sleep -Seconds 3
                        
                        # Restart llamafile in a new window
                        $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
                        $projectRoot = Split-Path -Parent $scriptPath
                        $llamafilePath = Join-Path $projectRoot "models\llamafile\llama-3.2-3b.exe"
                        Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '🚀 Auto-restarting Llamafile...' -ForegroundColor Cyan; & '$llamafilePath' --server --host 127.0.0.1 --port 8080 -ngl 999 -c 8192 --nobrowser"
                        
                        Write-Host "✓ Llamafile restarted" -ForegroundColor Green
                        Start-Sleep -Seconds 15  # Wait for restart
                        
                        $wasProcessing = $false
                        $lastIdleTime = Get-Date
                    } else {
                        Write-Host "⏳ Processing... (${duration.TotalSeconds}s)" -ForegroundColor Gray
                    }
                }
            } else {
                # Idle
                if ($wasProcessing) {
                    Write-Host "✓ Processing completed" -ForegroundColor Green
                }
                $wasProcessing = $false
                $lastIdleTime = Get-Date
            }
        }
        
    } catch {
        Write-Host "⚠️  Cannot connect to llamafile - may be down" -ForegroundColor Yellow
    }
}

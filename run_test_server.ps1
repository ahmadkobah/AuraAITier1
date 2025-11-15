# Test Server Runner - Windows PowerShell
# Runs test endpoints on port 8001
# Main app runs on port 8000

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AI Service Tier 1 - Test Server (Port 8001)                   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 Configuration:" -ForegroundColor Green
Write-Host "   • Main App:     http://localhost:8000" -ForegroundColor White
Write-Host "   • Test Server:  http://localhost:8001" -ForegroundColor Yellow
Write-Host ""

Write-Host "🧪 Available Test Endpoints:" -ForegroundColor Green
Write-Host "   GET  /test/health" -ForegroundColor Cyan
Write-Host "         Test the health status" -ForegroundColor Gray
Write-Host ""
Write-Host "   GET  /test/models" -ForegroundColor Cyan
Write-Host "         List all loaded models" -ForegroundColor Gray
Write-Host ""
Write-Host "   POST /test/simple-ocr?image_path=<path>" -ForegroundColor Cyan
Write-Host "         Test OCR on an image file" -ForegroundColor Gray
Write-Host ""
Write-Host "   POST /test/embedding?text=<text>" -ForegroundColor Cyan
Write-Host "         Test text embedding (all-MiniLM-L6-v2)" -ForegroundColor Gray
Write-Host ""
Write-Host "   POST /test/classification?text=<text>" -ForegroundColor Cyan
Write-Host "         Test zero-shot classification (all-MiniLM-L12-v2)" -ForegroundColor Gray
Write-Host ""

Write-Host "══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "ℹ️  Starting test server..." -ForegroundColor Yellow
Write-Host "    Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run test server
python -m uvicorn app.test_server:test_app --host 0.0.0.0 --port 8001 --log-level info

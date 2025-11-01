# OCR Service - Quick Start Guide

## Current Status

✅ **Service is Ready!** The OCR service has been successfully configured with:
- **Dual-Engine Support**: DeepSeek-VL OCR (advanced) + TrOCR (fallback)
- **GPU Acceleration**: CUDA 11.8 detected
- **Auto-Fallback**: Automatically switches to TrOCR if DeepSeek fails

## Starting the Service

### Method 1: PowerShell Script (Recommended)

**Start with TrOCR (Fast, works immediately):**
```powershell
cd python-ocr-service
.\start_ocr.ps1 -Engine trocr
```

**Start with DeepSeek (Advanced, requires model download):**
```powershell
cd python-ocr-service
.\start_ocr.ps1 -Engine deepseek
```

### Method 2: Direct Python

**TrOCR Mode:**
```powershell
cd python-ocr-service
$env:USE_DEEPSEEK_OCR='false'
python main.py
```

**DeepSeek Mode:**
```powershell
cd python-ocr-service
$env:USE_DEEPSEEK_OCR='true'
python main.py
```

## Testing the Service

Once running, open a **NEW** terminal and test:

```powershell
# Health check
curl http://localhost:8000/health

# OCR a file
curl -F "file=@path\to\image.jpg" http://localhost:8000/ocr/process
```

## Important Notes

### Why Service Shuts Down in Background

If you see the service start then immediately shut down, it's because:
- The terminal/VS Code background process management is terminating it
- **Solution**: Run in a dedicated terminal window that stays open

### TrOCR vs DeepSeek

**TrOCR (microsoft/trocr-base-printed)**
- ✅ Works immediately (no download)
- ✅ Fast inference (~1-2 seconds per page)
- ✅ Works on CPU or GPU
- ⚠️ Basic OCR (simple documents only)
- ⚠️ Struggles with: tables, multi-column, complex layouts

**DeepSeek-VL OCR**
- ✅ State-of-the-art accuracy
- ✅ Handles: tables, forms, complex layouts, equations
- ✅ Markdown output with structure preservation
- ⚠️ Requires: CUDA GPU + ~7GB model download
- ⚠️ First run: 5-10 minutes to download model
- ⚠️ Slower inference (~5-10 seconds per page)

### Recommendation

**For now: Use TrOCR**
- Start quickly
- Test your integration with Projectena
- Verify the service works end-to-end

**Later: Upgrade to DeepSeek**
- When you need better accuracy
- When you have complex documents
- After confirming GPU and storage space

## Next Steps

1. **Start TrOCR service** (using Method 1 or 2 above)
2. **Keep the terminal open** - don't close it!
3. **Test the /health endpoint** from another terminal
4. **Process a test image** to verify OCR works
5. **Integrate with Projectena** once OCR is working

## Troubleshooting

**Service won't start:**
```powershell
# Check if port 8000 is in use
netstat -ano | findstr ":8000"

# If something is using it, kill the process or use different port
$env:OCR_PORT='8001'
python main.py
```

**Import errors:**
```powershell
# Reinstall dependencies
pip install -r requirements.txt
```

**CUDA errors with DeepSeek:**
```powershell
# Fall back to TrOCR
$env:USE_DEEPSEEK_OCR='false'
python main.py
```

## Service Endpoints

Once running on `http://localhost:8000`:

- `GET /health` - Service health check
- `POST /ocr/process` - Process single file (quick)
- `POST /jobs` - Queue OCR job (asynchronous)
- `GET /jobs/{job_id}` - Get job status/result

See `DEEPSEEK_UPGRADE.md` for detailed API documentation.

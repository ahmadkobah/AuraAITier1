@echo off
echo Starting Adaptive Document Processing Services...
echo.

echo Starting OCR Service (Port 8000)...
start "OCR Service" cmd /c "cd /d %~dp0python-ocr-service && %~dp0.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info"

timeout /t 2 /nobreak > nul

echo Starting ICR Service (Port 8001)...
start "ICR Service" cmd /c "cd /d %~dp0python-icr-service && %~dp0.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --log-level info"

timeout /t 2 /nobreak > nul

echo Starting NLP Service (Port 8002)...
start "NLP Service" cmd /c "cd /d %~dp0python-nlp-service && %~dp0.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8002 --log-level info"

timeout /t 2 /nobreak > nul

echo Starting Document Intelligence Service (Port 8004)...
start "Document Intelligence" cmd /c "cd /d %~dp0python-document-intelligence-service && %~dp0.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8004 --log-level info"

echo.
echo All services started! Check individual command windows for status.
echo.
echo Service URLs:
echo - OCR Service: http://127.0.0.1:8000
echo - ICR Service: http://127.0.0.1:8001
echo - NLP Service: http://127.0.0.1:8002
echo - Document Intelligence: http://127.0.0.1:8004
echo.
pause
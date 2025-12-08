@echo off
echo Starting AI Service with Poppler configured...
echo.

cd /d "C:\Users\Ahmad\OneDrive\Documents\GitHub\adaptive-Dokumentenverarbeitung"

REM Add Poppler to PATH for this session
set PATH=%PATH%;C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin

REM Verify Poppler is accessible
echo Checking Poppler...
pdftoppm -v 2>&1 | findstr /C:"version"
if errorlevel 1 (
    echo ERROR: Poppler not found!
    pause
    exit /b 1
)

echo.
echo Poppler OK - Starting AI Service on port 9000...
echo.

REM Start the AI service
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 9000

pause

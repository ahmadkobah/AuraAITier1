@echo off
echo ========================================
echo Adaptive Document Processing Startup
echo ========================================
echo.

set BASEPATH=%~dp0..
set LLAMAFILE=%BASEPATH%\models\llamafile\llama-3.2-3b.exe

REM Check if llamafile exists
if not exist "%LLAMAFILE%" (
    echo ERROR: Llamafile not found at: %LLAMAFILE%
    echo.
    echo Please download from:
    echo https://huggingface.co/Mozilla/Llama-3.2-3B-Instruct-llamafile/resolve/main/Llama-3.2-3B-Instruct.Q6_K.llamafile
    echo.
    echo Save as: llama-3.2-3b.llamafile
    pause
    exit /b 1
)

echo Starting Llamafile Server (Port 8080)...
echo   Model: Llama 3.2 3B Instruct (Q6_K)
echo   GPU: Enabled (auto-detect)
echo   Context: 8192 tokens
echo.

start "Llamafile Server" "%LLAMAFILE%" --server --host 127.0.0.1 --port 8080 -ngl 999 -c 8192 --nobrowser

timeout /t 5 /nobreak > nul

echo Starting FastAPI Document Processing Service (Port 9000)...
echo   API: http://127.0.0.1:9000
echo   Docs: http://127.0.0.1:9000/docs
echo.

start "FastAPI Service" cmd /c "cd /d %BASEPATH% && %BASEPATH%\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 9000 --reload"

echo.
echo ========================================
echo Services Started Successfully!
echo ========================================
echo.
echo Service URLs:
echo   - Llamafile API: http://127.0.0.1:8080
echo   - FastAPI Service: http://127.0.0.1:9000
echo   - API Documentation: http://127.0.0.1:9000/docs
echo.
echo To stop services: Close the command windows
echo.
pause

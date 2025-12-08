@echo off
echo.
echo ========================================
echo CUDA Integration Setup
echo ========================================
echo.
echo This will install CUDA 11.8 integration files into Visual Studio 2026
echo Administrator privileges are required.
echo.
pause

PowerShell -Command "Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0setup_cuda_integration.ps1""' -Verb RunAs"

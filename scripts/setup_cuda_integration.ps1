# CUDA Integration Setup Script for Visual Studio 2026
# This script must be run as Administrator

Write-Host "=== CUDA 11.8 Integration with Visual Studio 2026 ===" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    pause
    exit 1
}

# Define paths
$cudaIntegrationSource = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\extras\visual_studio_integration\MSBuildExtensions"
$vsDestination = "C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Microsoft\VC\v180\BuildCustomizations"

# Check if CUDA files exist
if (-not (Test-Path $cudaIntegrationSource)) {
    Write-Host "ERROR: CUDA integration files not found at: $cudaIntegrationSource" -ForegroundColor Red
    Write-Host "Please ensure CUDA Toolkit 11.8 is installed correctly." -ForegroundColor Yellow
    pause
    exit 1
}

# Check if VS directory exists
if (-not (Test-Path $vsDestination)) {
    Write-Host "ERROR: Visual Studio BuildCustomizations directory not found at: $vsDestination" -ForegroundColor Red
    Write-Host "Please ensure Visual Studio 2026 with C++ tools is installed correctly." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "Source: $cudaIntegrationSource" -ForegroundColor Gray
Write-Host "Destination: $vsDestination" -ForegroundColor Gray
Write-Host ""

# Copy files
try {
    Write-Host "Copying CUDA integration files..." -ForegroundColor Yellow
    
    $filesToCopy = Get-ChildItem -Path $cudaIntegrationSource -File
    $copiedCount = 0
    
    foreach ($file in $filesToCopy) {
        Write-Host "  Copying: $($file.Name)" -ForegroundColor Gray
        Copy-Item -Path $file.FullName -Destination $vsDestination -Force -ErrorAction Stop
        $copiedCount++
    }
    
    Write-Host ""
    Write-Host "SUCCESS: Copied $copiedCount file(s) successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Verify files were copied
    Write-Host "Verifying installation..." -ForegroundColor Yellow
    $cudaTargetsFile = Join-Path $vsDestination "CUDA 11.8.targets"
    if (Test-Path $cudaTargetsFile) {
        Write-Host "✓ CUDA 11.8.targets found" -ForegroundColor Green
    } else {
        Write-Host "✗ CUDA 11.8.targets NOT found" -ForegroundColor Red
    }
    
    $cudaPropsFile = Join-Path $vsDestination "CUDA 11.8.props"
    if (Test-Path $cudaPropsFile) {
        Write-Host "✓ CUDA 11.8.props found" -ForegroundColor Green
    } else {
        Write-Host "✗ CUDA 11.8.props NOT found" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "CUDA integration setup complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Return to VS Code" -ForegroundColor White
    Write-Host "2. Rebuild llama-cpp-python with: pip uninstall llama-cpp-python" -ForegroundColor White
    Write-Host "3. Then: pip install llama-cpp-python --force-reinstall --no-cache-dir" -ForegroundColor White
    Write-Host "   with CMAKE_ARGS='-DGGML_CUDA=on'" -ForegroundColor White
    
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to copy files!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Gray
pause

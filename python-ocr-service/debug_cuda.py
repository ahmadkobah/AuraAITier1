"""Debug script to check CUDA and environment configuration"""
import os
import sys
import torch

print("=" * 60)
print("🔍 CUDA & Environment Debug")
print("=" * 60)
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print()
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU device: {torch.cuda.get_device_name(0)}")
    print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
print()
print("Environment Variables:")
print(f"  USE_DEEPSEEK_OCR = {os.getenv('USE_DEEPSEEK_OCR', 'NOT SET')}")
print(f"  DEEPSEEK_MODEL_PATH = {os.getenv('DEEPSEEK_MODEL_PATH', 'NOT SET')}")
print()
print("Configuration Logic:")
USE_DEEPSEEK = os.getenv("USE_DEEPSEEK_OCR", "true").lower() == "true"
print(f"  USE_DEEPSEEK = {USE_DEEPSEEK}")
if USE_DEEPSEEK and not torch.cuda.is_available():
    print(f"  ⚠️  Would fall back to TrOCR (CUDA not available)")
elif USE_DEEPSEEK and torch.cuda.is_available():
    print(f"  ✅ Would use DeepSeek OCR")
else:
    print(f"  ℹ️  Would use TrOCR (USE_DEEPSEEK_OCR=false)")
print("=" * 60)

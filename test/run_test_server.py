#!/usr/bin/env python
"""
Test Server Launcher
Runs test endpoints on port 8001 (separate from main app on 8080)
"""

import subprocess
import sys
import time
import os

def run_test_server():
    """Start the test server"""
    print("=" * 70)
    print("AI Service Tier 1 - Test Server")
    print("=" * 70)
    print()
    print("📊 Configuration:")
    print("  • Main App:  http://localhost:8080")
    print("  • Test Server: http://localhost:8001")
    print()
    print("🧪 Available Test Endpoints:")
    print("  • GET  /test/health           - Health check")
    print("  • GET  /test/models           - List loaded models")
    print("  • POST /test/simple-ocr?image_path=... - Test OCR")
    print("  • POST /test/embedding?text=... - Test embeddings")
    print("  • POST /test/classification?text=... - Test classification")
    print()
    print("=" * 70)
    print()
    
    # Check if main app is running
    print("Checking if main app is running on port 8080...")
    time.sleep(1)
    
    try:
        import requests
        response = requests.get("http://localhost:8080/health", timeout=2)
        if response.status_code == 200:
            print("✅ Main app is running on port 8080")
        else:
            print("⚠️  Main app might not be responding correctly")
    except:
        print("⚠️  Could not reach main app on port 8080")
        print("   Make sure to run: uvicorn app.main:app --port 8080")
    
    print()
    print("Starting test server on port 8001...")
    print()
    
    # Run test server
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.test_server:test_app",
        "--host", "0.0.0.0",
        "--port", "8001",
        "--log-level", "info"
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\nTest server stopped.")
        sys.exit(0)

if __name__ == "__main__":
    run_test_server()

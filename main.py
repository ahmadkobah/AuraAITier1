"""
================================================================================
Adaptive Document Processing - AI Service
Main Entry Point
================================================================================

OVERVIEW:
---------
This is the main entry point for the AI Document Processing Service.
It orchestrates the startup of all required services and the FastAPI server.

SERVICES STARTED:
----------------
1. LLaMA 3.2 3B Server (port 8080) - For Q&A and summarization
2. FastAPI Application (port 9000) - Main REST API server

USAGE:
------
    # Start all services (LLaMA + FastAPI)
    python main.py
    
    # Start only FastAPI (requires LLaMA already running)
    uvicorn main:app --host 0.0.0.0 --port 9000
    
    # Development mode with auto-reload
    uvicorn main:app --reload --host 0.0.0.0 --port 9000

ENDPOINTS AVAILABLE:
-------------------
    - http://localhost:9000/docs          - Interactive API documentation
    - http://localhost:9000/health        - Health check endpoint
    - http://localhost:9000/api/v1/...    - Main API routes
    - http://localhost:8080               - LLaMA server (internal)

REQUIREMENTS:
------------
    - Python 3.9+
    - MongoDB running (local or Atlas)
    - NVIDIA GPU (optional, falls back to CPU)
    - LLaMA model in models/llamafile/

ENVIRONMENT VARIABLES:
---------------------
    PORT=9000                    - FastAPI server port
    DB=mongodb://...             - MongoDB connection string
    GPU_ON_DEMAND=true           - Enable on-demand GPU loading
    AUTO_CLEANUP_GPU=true        - Clear GPU cache after inference

================================================================================
"""

# ========================
# Standard Library Imports
# ========================
import os
import sys
import subprocess
import time
import logging
import signal
import atexit
from pathlib import Path

# ========================
# Local Application Imports
# ========================
from app.api.endpoints import app

# Export the FastAPI app instance for uvicorn
__all__ = ['app']

# ========================
# Logging Configuration
# ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========================
# Service Startup Functions
# ========================

def start_llamafile():
    """
    Start the LLaMA 3.2 3B server in the background.
    
    This function launches the LLaMA model server which provides:
    - Question answering capabilities
    - Document summarization
    - Text generation
    
    The server runs on port 8080 and uses all available GPU layers
    for maximum performance.
    
    Returns:
        subprocess.Popen: The LLaMA process handle, or None if failed to start
        
    Port Check:
        If port 8080 is already in use, assumes an existing LLaMA instance
        is running and returns None.
        
    Logs:
        All LLaMA output is written to logs/llama.log for debugging.
    """
    llamafile_path = Path(__file__).parent / "models" / "llamafile" / "llama-3.2-3b.exe"
    log_path = Path(__file__).parent / "logs" / "llama.log"
    
    if not llamafile_path.exists():
        print(f"❌ Llamafile not found at: {llamafile_path}")
        return None
    
    # Check if port is already in use
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8080))
    sock.close()
    if result == 0:
        print("⚠️  Port 8080 already in use - attempting to use existing Llamafile")
        return None
    
    try:
        # Ensure logs directory exists
        log_path.parent.mkdir(exist_ok=True)
        
        # Open log file
        log_file = open(log_path, 'w')
        
        process = subprocess.Popen(
            [
                str(llamafile_path),
                "--server",
                "--host", "127.0.0.1",
                "--port", "8080",
                "-ngl", "999",  # Use all GPU layers
                "-c", "8192",   # Context window
                "--nobrowser"
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        time.sleep(2)  # Brief pause to let process start
        
        # Check if process is still alive
        if process.poll() is not None:
            print(f"❌ Llamafile failed to start - check {log_path}")
            return None
            
        return process
    except Exception as e:
        print(f"❌ Failed to start Llamafile: {e}")
        return None


def check_mongodb():
    """
    Check if MongoDB is accessible.
    
    Attempts to connect to the local MongoDB instance and verify
    it's responding to commands. This is a quick health check to
    ensure the database is available before starting the service.
    
    Returns:
        bool: True if MongoDB is accessible, False otherwise
        
    Notes:
        - Uses a 2-second timeout for quick startup
        - Only checks localhost - production uses MongoDB Atlas
        - Non-critical check - service can start without MongoDB
    """
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure
    
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        print("✅ MongoDB: Connected")
        return True
    except:
        print("⚠️  MongoDB: Not running (start with: net start MongoDB)")
        return False


# ========================
# Main Application Entry Point
# ========================

if __name__ == "__main__":
    """
    Application startup sequence:
    
    1. Display startup banner
    2. Check MongoDB availability (optional)
    3. Start LLaMA server on port 8080
    4. Wait for LLaMA to be ready (health check)
    5. Start FastAPI server on port 9000
    6. Display service URLs
    7. Handle graceful shutdown on Ctrl+C
    
    The application will continue even if MongoDB or LLaMA fail to start,
    but functionality will be limited.
    """
    print("\n" + "="*60)
    print("🚀 Adaptive Document Processing")
    print("="*60 + "\n")
    
    # Check MongoDB (silent check)
    mongo_ok = check_mongodb()
    
    # Start Llamafile
    print("Starting Llamafile server...")
    llamafile_process = start_llamafile()
    
    # Wait for Llamafile to be fully ready
    llamafile_ready = False
    if llamafile_process:
        import requests
        max_retries = 90  # Wait up to 90 seconds
        for i in range(max_retries):
            # Check if process crashed
            if llamafile_process.poll() is not None:
                print(f"❌ Llamafile: Process crashed - check logs/llama.log\n")
                break
                
            try:
                response = requests.get("http://127.0.0.1:8080/health", timeout=1)
                if response.status_code == 200:
                    print(f"✅ Llamafile: Ready (started in {i+1}s)\n")
                    llamafile_ready = True
                    break
            except:
                pass
            if i % 10 == 0 and i > 0:
                print(f"   Still loading... ({i}s)")
            time.sleep(1)
        else:
            print("❌ Llamafile: Timeout after 90s - check logs/llama.log\n")
    else:
        # Try to connect to existing Llamafile on port 8080
        import requests
        try:
            response = requests.get("http://127.0.0.1:8080/health", timeout=2)
            if response.status_code == 200:
                print("✅ Llamafile: Connected to existing instance\n")
                llamafile_ready = True
        except:
            print("❌ Llamafile: Not available\n")
    
    # Start FastAPI
    print("Starting FastAPI service...\n")
    print("="*60)
    print("✅ Services Ready")
    print("="*60)
    print("\n📍 URLs:")
    print("   • FastAPI: http://127.0.0.1:9000")
    print("   • API Docs: http://127.0.0.1:9000/docs")
    print("   • Llamafile: http://127.0.0.1:8080")
    print("\n⌨️  Press Ctrl+C to stop\n")
    
    def cleanup_llamafile():
        """Kill all LlamaFile processes to free GPU memory."""
        print("\n🧹 Cleaning up LlamaFile...")
        if llamafile_process:
            try:
                llamafile_process.terminate()
                llamafile_process.wait(timeout=5)
                print("✅ LlamaFile terminated (owned process)")
            except Exception as e:
                print(f"⚠️ Error terminating LlamaFile: {e}")
        
        # Always try to kill by name as backup (in case we connected to existing instance)
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['taskkill', '/F', '/IM', 'llama-3.2-3b.exe'], 
                               capture_output=True, timeout=5, text=True)
                if result.returncode == 0:
                    print("✅ LlamaFile killed (taskkill)")
            else:
                subprocess.run(['pkill', '-f', 'llama-3.2-3b'], 
                               capture_output=True, timeout=5)
        except Exception as e:
            pass  # Process might already be dead
    
    # Register cleanup to run on ANY exit (normal, exception, signal)
    atexit.register(cleanup_llamafile)
    
    # Also handle SIGTERM (docker stop, systemctl stop, etc.)
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down...")
        cleanup_llamafile()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    if sys.platform != 'win32':
        signal.signal(signal.SIGHUP, signal_handler)
    
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=9000, log_level="error")
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down (Ctrl+C)...")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
    finally:
        # atexit will call cleanup_llamafile, but call it explicitly too for clarity
        cleanup_llamafile()
        print("✅ Stopped\n")

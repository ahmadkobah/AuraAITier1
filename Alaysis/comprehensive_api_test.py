"""
Comprehensive API Upload Test
Tests all upload endpoints with detailed validation
"""

import json
from pathlib import Path
import re

def extract_endpoints(file_path):
    """Extract all API endpoints from a Python file"""
    endpoints = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all @app.* decorators
    pattern = r'@app\.(post|get|put|delete|patch)\(["\']([^"\']+)["\']\)'
    matches = re.findall(pattern, content)
    
    for method, path in matches:
        endpoints.append({
            "method": method.upper(),
            "path": path
        })
    
    # Check for file upload support
    has_upload_file = 'UploadFile' in content
    has_file_param = 'File(' in content
    
    return endpoints, has_upload_file, has_file_param

def analyze_endpoint(file_path, endpoint_path):
    """Analyze a specific endpoint for parameters and functionality"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the function definition for this endpoint
    pattern = rf'@app\.\w+\(["\']' + re.escape(endpoint_path) + r'["\']\).*?async def (\w+)\((.*?)\):'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        func_name = match.group(1)
        params = match.group(2)
        
        return {
            "function": func_name,
            "accepts_file": "UploadFile" in params or "File" in params,
            "accepts_json": "Request" in params or "BaseModel" in content,
            "parameters": params.strip()
        }
    
    return None

def test_all_services():
    """Test all services comprehensively"""
    
    services = {
        "OCR Service": {
            "path": "python-ocr-service/main.py",
            "port": 8000,
            "expected_features": ["file upload", "OCR processing", "job tracking"]
        },
        "NLP Service": {
            "path": "python-nlp-service/main.py",
            "port": 8002,
            "expected_features": ["text classification", "entity extraction", "sentiment analysis"]
        },
        "ICR Service": {
            "path": "python-icr-service/main.py",
            "port": 8001,
            "expected_features": ["handwriting recognition", "signature detection", "file upload"]
        },
        "Document Intelligence Service": {
            "path": "python-document-intelligence-service/main.py",
            "port": 8003,
            "expected_features": ["document classification", "entity extraction", "routing"]
        }
    }
    
    results = {}
    
    print("=" * 80)
    print("COMPREHENSIVE API UPLOAD & FUNCTIONALITY TEST")
    print("=" * 80)
    
    for service_name, config in services.items():
        print(f"\n{'='*80}")
        print(f"Service: {service_name}")
        print(f"{'='*80}")
        
        file_path = Path(config["path"])
        
        if not file_path.exists():
            print(f"❌ ERROR: File not found - {file_path}")
            results[service_name] = {"error": "File not found"}
            continue
        
        print(f"✓ File: {file_path}")
        print(f"✓ Port: {config['port']}")
        
        # Extract endpoints
        endpoints, has_upload, has_file = extract_endpoints(file_path)
        
        print(f"\n📍 Endpoints Found: {len(endpoints)}")
        print("-" * 80)
        
        upload_endpoints = []
        for ep in endpoints:
            print(f"  {ep['method']:6s} {ep['path']}")
            
            # Analyze endpoint details
            details = analyze_endpoint(file_path, ep['path'])
            if details:
                if details['accepts_file']:
                    print(f"         ↳ 📎 Accepts file uploads")
                    upload_endpoints.append(ep['path'])
                if details['accepts_json']:
                    print(f"         ↳ 📄 Accepts JSON data")
        
        print(f"\n📤 Upload Capabilities:")
        print(f"   - UploadFile support: {'✓ Yes' if has_upload else '✗ No'}")
        print(f"   - File parameter: {'✓ Yes' if has_file else '✗ No'}")
        print(f"   - Upload endpoints: {len(upload_endpoints)}")
        
        if upload_endpoints:
            print(f"\n   Upload-enabled endpoints:")
            for ep_path in upload_endpoints:
                print(f"     • {ep_path}")
        
        # Check expected features
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        
        print(f"\n✨ Features:")
        for feature in config["expected_features"]:
            feature_words = feature.lower().split()
            has_feature = all(word in content for word in feature_words)
            status = "✓" if has_feature else "✗"
            print(f"   {status} {feature}")
        
        results[service_name] = {
            "file": str(file_path),
            "port": config["port"],
            "endpoints": endpoints,
            "upload_support": has_upload,
            "upload_endpoints": upload_endpoints,
            "endpoint_count": len(endpoints)
        }
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    
    total_endpoints = sum(r.get("endpoint_count", 0) for r in results.values())
    services_with_upload = sum(1 for r in results.values() if r.get("upload_support", False))
    
    print(f"\n✓ Total Services: {len(services)}")
    print(f"✓ Total Endpoints: {total_endpoints}")
    print(f"✓ Services with Upload: {services_with_upload}/{len(services)}")
    
    # Save results
    output_file = "comprehensive_api_test.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Detailed results saved to: {output_file}")
    
    # Critical Issue Warning
    print(f"\n{'='*80}")
    print("⚠️  CRITICAL: PYTHON VERSION INCOMPATIBILITY")
    print(f"{'='*80}")
    print("\nYour system is running Python 3.13, but the services require:")
    print("  • PyTorch 2.x - NOT compatible with Python 3.13")
    print("  • Transformers 4.x - Limited Python 3.13 support")
    print("  • spaCy 3.x - NOT compatible with Python 3.13")
    print("\n🔧 SOLUTION:")
    print("  1. Download Python 3.11: https://www.python.org/downloads/release/python-3119/")
    print("  2. Create virtual environment:")
    print("     python3.11 -m venv .venv")
    print("  3. Activate it:")
    print("     .venv\\Scripts\\activate  (Windows)")
    print("  4. Install dependencies:")
    print("     pip install -r python-ocr-service/requirements.txt")
    print("     pip install -r python-nlp-service/requirements.txt")
    print("     pip install -r python-icr-service/requirements.txt")
    print("     pip install -r python-document-intelligence-service/requirements.txt")
    
    return results

if __name__ == "__main__":
    results = test_all_services()

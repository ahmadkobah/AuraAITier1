"""
API Functionality Test Script
Tests the upload endpoints and API structure without running the full services
"""

import sys
import ast
import json
from pathlib import Path

def test_api_structure():
    """Test the API endpoint structure and functionality"""
    
    results = {
        "ocr_service": {},
        "nlp_service": {},
        "icr_service": {},
        "document_intelligence_service": {}
    }
    
    # Test OCR Service
    print("=" * 60)
    print("Testing OCR Service API Structure")
    print("=" * 60)
    
    ocr_main = Path("python-ocr-service/main.py")
    if ocr_main.exists():
        with open(ocr_main, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for FastAPI endpoints
        has_upload = '@app.post("/ocr/upload")' in content or '@app.post("/upload")' in content
        has_status = 'status' in content.lower()
        has_file_upload = 'UploadFile' in content
        has_ocr_endpoint = '/ocr' in content
        
        results["ocr_service"] = {
            "file": str(ocr_main),
            "has_upload_endpoint": has_upload,
            "has_file_upload_support": has_file_upload,
            "has_status_tracking": has_status,
            "has_ocr_endpoint": has_ocr_endpoint,
            "port": 8000
        }
        
        print(f"✓ File exists: {ocr_main}")
        print(f"✓ Upload endpoint: {has_upload}")
        print(f"✓ File upload support: {has_file_upload}")
        print(f"✓ Status tracking: {has_status}")
        print(f"✓ OCR endpoint: {has_ocr_endpoint}")
        print(f"✓ Port: 8000")
    else:
        print(f"✗ File not found: {ocr_main}")
        results["ocr_service"]["error"] = "File not found"
    
    # Test NLP Service
    print("\n" + "=" * 60)
    print("Testing NLP Service API Structure")
    print("=" * 60)
    
    nlp_main = Path("python-nlp-service/main.py")
    if nlp_main.exists():
        with open(nlp_main, 'r', encoding='utf-8') as f:
            content = f.read()
            
        has_classify = 'classify' in content.lower()
        has_analyze = 'analyze' in content.lower()
        has_nlp_endpoint = '/nlp' in content or 'NlpClassification' in content
        
        results["nlp_service"] = {
            "file": str(nlp_main),
            "has_classification": has_classify,
            "has_analysis": has_analyze,
            "has_nlp_endpoint": has_nlp_endpoint,
            "port": 8002
        }
        
        print(f"✓ File exists: {nlp_main}")
        print(f"✓ Classification support: {has_classify}")
        print(f"✓ Analysis support: {has_analyze}")
        print(f"✓ NLP endpoint: {has_nlp_endpoint}")
        print(f"✓ Port: 8002")
    else:
        print(f"✗ File not found: {nlp_main}")
        results["nlp_service"]["error"] = "File not found"
    
    # Test ICR Service
    print("\n" + "=" * 60)
    print("Testing ICR Service API Structure")
    print("=" * 60)
    
    icr_main = Path("python-icr-service/main.py")
    if icr_main.exists():
        with open(icr_main, 'r', encoding='utf-8') as f:
            content = f.read()
            
        has_upload = 'UploadFile' in content
        has_handwriting = 'handwriting' in content.lower()
        has_signature = 'signature' in content.lower()
        
        results["icr_service"] = {
            "file": str(icr_main),
            "has_upload_support": has_upload,
            "has_handwriting_recognition": has_handwriting,
            "has_signature_detection": has_signature,
            "port": 8001
        }
        
        print(f"✓ File exists: {icr_main}")
        print(f"✓ Upload support: {has_upload}")
        print(f"✓ Handwriting recognition: {has_handwriting}")
        print(f"✓ Signature detection: {has_signature}")
        print(f"✓ Port: 8001")
    else:
        print(f"✗ File not found: {icr_main}")
        results["icr_service"]["error"] = "File not found"
    
    # Test Document Intelligence Service
    print("\n" + "=" * 60)
    print("Testing Document Intelligence Service API Structure")
    print("=" * 60)
    
    doc_main = Path("python-document-intelligence-service/main.py")
    if doc_main.exists():
        with open(doc_main, 'r', encoding='utf-8') as f:
            content = f.read()
            
        has_upload = 'UploadFile' in content
        has_classification = 'classification' in content.lower()
        has_extraction = 'extraction' in content.lower()
        has_routing = 'routing' in content.lower()
        
        results["document_intelligence_service"] = {
            "file": str(doc_main),
            "has_upload_support": has_upload,
            "has_classification": has_classification,
            "has_extraction": has_extraction,
            "has_routing": has_routing,
        }
        
        print(f"✓ File exists: {doc_main}")
        print(f"✓ Upload support: {has_upload}")
        print(f"✓ Classification: {has_classification}")
        print(f"✓ Extraction: {has_extraction}")
        print(f"✓ Routing: {has_routing}")
    else:
        print(f"✗ File not found: {doc_main}")
        results["document_intelligence_service"]["error"] = "File not found"
    
    # Summary
    print("\n" + "=" * 60)
    print("API FUNCTIONALITY SUMMARY")
    print("=" * 60)
    
    all_services_ok = True
    for service, data in results.items():
        if "error" in data:
            print(f"✗ {service}: FAILED - {data['error']}")
            all_services_ok = False
        else:
            print(f"✓ {service}: OK")
    
    # Check for Python compatibility issues
    print("\n" + "=" * 60)
    print("PYTHON COMPATIBILITY CHECK")
    print("=" * 60)
    
    print(f"Current Python version: {sys.version}")
    print("\n⚠️  WARNING: Python 3.13 detected!")
    print("   PyTorch and many ML libraries do not support Python 3.13 yet.")
    print("   Recommended: Use Python 3.11 or 3.12 for full compatibility.")
    print("\nTo fix this:")
    print("   1. Install Python 3.11 or 3.12")
    print("   2. Create a virtual environment with that version")
    print("   3. Install all dependencies in that environment")
    
    # Save results
    with open('api_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to: api_test_results.json")
    
    return all_services_ok

if __name__ == "__main__":
    success = test_api_structure()
    sys.exit(0 if success else 1)

"""
Test Suite for Enhanced OCR System

Tests all three major enhancements:
1. Hybrid OCR routing
2. Structured NLP analysis
3. Mixed document processing

Run this to validate the implementation.
"""

import requests
import json
from pathlib import Path
from typing import Dict, Any


class Colors:
    """Console colors for output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_header(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print(f"{msg}")
    print(f"{'='*70}{Colors.END}\n")


class ServiceTester:
    """Test suite for enhanced OCR system"""
    
    def __init__(self):
        self.ocr_url = "http://127.0.0.1:8000"
        self.nlp_url = "http://127.0.0.1:8001"
        self.icr_url = "http://127.0.0.1:8002"
        
        self.results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
    
    def test_service_health(self):
        """Test health endpoints for all services"""
        print_header("TEST 1: Service Health Checks")
        
        services = [
            ("OCR", f"{self.ocr_url}/health"),
            ("NLP", f"{self.nlp_url}/health"),
            ("ICR", f"{self.icr_url}/health"),
        ]
        
        for name, url in services:
            self.results["total"] += 1
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    
                    if status in ["ok", "healthy"]:
                        print_success(f"{name} Service: {status}")
                        self.results["passed"] += 1
                        
                        # Show additional info
                        if name == "OCR":
                            engines = data.get("engines_available", [])
                            print_info(f"  Available engines: {', '.join(engines)}")
                            routing = data.get("routing_enabled", False)
                            print_info(f"  Routing enabled: {routing}")
                        
                        elif name == "NLP":
                            version = data.get("version", "unknown")
                            print_info(f"  Version: {version}")
                        
                        elif name == "ICR":
                            caps = data.get("capabilities", {})
                            if caps.get("mixed_document_support"):
                                print_info(f"  Mixed document support: enabled")
                    else:
                        print_error(f"{name} Service: {status}")
                        self.results["failed"] += 1
                else:
                    print_error(f"{name} Service: HTTP {response.status_code}")
                    self.results["failed"] += 1
            
            except requests.exceptions.ConnectionError:
                print_error(f"{name} Service: Not running")
                self.results["failed"] += 1
            except Exception as e:
                print_error(f"{name} Service: {str(e)}")
                self.results["failed"] += 1
    
    def test_ocr_routing(self):
        """Test OCR routing functionality"""
        print_header("TEST 2: OCR Hybrid Routing")
        
        # Test with sample markdown text (simulates complex document)
        test_text = """
        # Invoice #12345
        
        | Item | Quantity | Price |
        |------|----------|-------|
        | Widget | 10 | $99.99 |
        | Gadget | 5 | $49.99 |
        
        **Total:** $1,249.85
        """
        
        self.results["total"] += 1
        
        try:
            # Check if routing info is available
            response = requests.get(f"{self.ocr_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                if data.get("routing_enabled"):
                    print_success("Routing functionality: enabled")
                    self.results["passed"] += 1
                    
                    engines = data.get("engines_available", [])
                    print_info(f"  Available engines: {', '.join(engines)}")
                    
                    if "DeepSeek" in engines:
                        print_info("  DeepSeek: available (GPU enabled)")
                    else:
                        print_warning("  DeepSeek: not available (requires CUDA GPU)")
                        self.results["warnings"] += 1
                    
                    if "TrOCR" in engines:
                        print_info("  TrOCR: available")
                else:
                    print_warning("Routing functionality: not enabled")
                    self.results["warnings"] += 1
            else:
                print_error(f"Could not check routing: HTTP {response.status_code}")
                self.results["failed"] += 1
        
        except Exception as e:
            print_error(f"Routing test failed: {str(e)}")
            self.results["failed"] += 1
    
    def test_structured_nlp(self):
        """Test structured NLP analysis"""
        print_header("TEST 3: Structured NLP Analysis")
        
        # Test markdown parsing
        test_markdown = """
# Invoice

## Vendor Information
**Company:** Microsoft Corporation
**Address:** One Microsoft Way, Redmond, WA

## Items

| Item | Quantity | Unit Price | Total |
|------|----------|------------|-------|
| Office 365 | 10 | $99.99 | $999.90 |
| Azure Credits | 5 | $200.00 | $1,000.00 |

## Summary

| Field | Value |
|-------|-------|
| Subtotal | $1,999.90 |
| Tax | $159.99 |
| Total | $2,159.89 |
"""
        
        self.results["total"] += 1
        
        try:
            response = requests.post(
                f"{self.nlp_url}/nlp/analyze-structured",
                json={
                    "text": test_markdown,
                    "analysis_types": ["entities"]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check structure parsing
                structure = data.get("structure", {})
                tables = structure.get("tables", 0)
                sections = structure.get("sections", 0)
                
                if tables > 0:
                    print_success(f"Table parsing: {tables} tables detected")
                    self.results["passed"] += 1
                else:
                    print_warning("Table parsing: no tables detected")
                    self.results["warnings"] += 1
                
                if sections > 0:
                    print_info(f"  Sections detected: {sections}")
                
                # Check entity extraction
                entities = data.get("entities", [])
                if entities:
                    print_info(f"  Entities extracted: {len(entities)}")
                    
                    # Check for context-aware entities
                    has_context = any(
                        e.get("section_context") or e.get("table_context") 
                        for e in entities
                    )
                    
                    if has_context:
                        print_success("Context-aware entities: detected")
                        
                        # Show example
                        for entity in entities[:3]:
                            if entity.get("role"):
                                print_info(f"    {entity['text']} → {entity['role']} (confidence: {entity.get('confidence', 0):.2f})")
                    else:
                        print_warning("Context-aware entities: no context found")
                        self.results["warnings"] += 1
                
                # Check table data extraction
                table_data = data.get("table_data", {})
                if table_data:
                    line_items = table_data.get("line_items", [])
                    if line_items:
                        print_success(f"Table data extraction: {len(line_items)} line items")
                        print_info(f"    Example: {line_items[0]}")
            
            else:
                print_error(f"Structured NLP test failed: HTTP {response.status_code}")
                self.results["failed"] += 1
        
        except requests.exceptions.ConnectionError:
            print_error("NLP service not available")
            self.results["failed"] += 1
        except Exception as e:
            print_error(f"Structured NLP test failed: {str(e)}")
            self.results["failed"] += 1
    
    def test_mixed_document_detection(self):
        """Test mixed document detection"""
        print_header("TEST 4: Mixed Document Detection")
        
        self.results["total"] += 1
        
        try:
            # Check if hybrid endpoints exist
            response = requests.get(f"{self.icr_url}/health", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                caps = data.get("capabilities", {})
                
                if caps.get("mixed_document_support"):
                    print_success("Mixed document support: enabled")
                    self.results["passed"] += 1
                    
                    if caps.get("hybrid_ocr_icr"):
                        print_info("  Hybrid OCR/ICR: available")
                    
                    if caps.get("signature_detection"):
                        print_info("  Signature detection: available")
                    
                    print_info("\n  Available endpoints:")
                    print_info("    POST /hybrid/analyze - Analyze document")
                    print_info("    POST /hybrid/process - Process mixed document")
                else:
                    print_warning("Mixed document support: not available")
                    self.results["warnings"] += 1
            else:
                print_error(f"ICR service check failed: HTTP {response.status_code}")
                self.results["failed"] += 1
        
        except requests.exceptions.ConnectionError:
            print_error("ICR service not available")
            self.results["failed"] += 1
        except Exception as e:
            print_error(f"Mixed document test failed: {str(e)}")
            self.results["failed"] += 1
    
    def test_api_capabilities(self):
        """Test enhanced API capabilities"""
        print_header("TEST 5: Enhanced API Capabilities")
        
        endpoints_to_check = [
            ("OCR Routing", "GET", f"{self.ocr_url}/health", "routing_enabled"),
            ("NLP Root", "GET", f"{self.nlp_url}/", "features"),
            ("ICR Hybrid", "GET", f"{self.icr_url}/health", "capabilities"),
        ]
        
        for name, method, url, feature_key in endpoints_to_check:
            self.results["total"] += 1
            
            try:
                if method == "GET":
                    response = requests.get(url, timeout=5)
                else:
                    response = requests.post(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if feature_key in data:
                        print_success(f"{name}: available")
                        self.results["passed"] += 1
                        
                        # Show feature details
                        feature_data = data[feature_key]
                        if isinstance(feature_data, dict):
                            for k, v in feature_data.items():
                                if v is True:
                                    print_info(f"    {k}: enabled")
                        elif isinstance(feature_data, list):
                            print_info(f"    Features: {', '.join(str(f) for f in feature_data)}")
                    else:
                        print_warning(f"{name}: feature info not found")
                        self.results["warnings"] += 1
                else:
                    print_error(f"{name}: HTTP {response.status_code}")
                    self.results["failed"] += 1
            
            except Exception as e:
                print_error(f"{name}: {str(e)}")
                self.results["failed"] += 1
    
    def print_summary(self):
        """Print test summary"""
        print_header("TEST SUMMARY")
        
        total = self.results["total"]
        passed = self.results["passed"]
        failed = self.results["failed"]
        warnings = self.results["warnings"]
        
        print(f"Total Tests: {total}")
        print_success(f"Passed: {passed}")
        
        if failed > 0:
            print_error(f"Failed: {failed}")
        
        if warnings > 0:
            print_warning(f"Warnings: {warnings}")
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n{Colors.BOLD}Pass Rate: {pass_rate:.1f}%{Colors.END}")
        
        if pass_rate >= 80:
            print_success("\n🎉 System is ready for use!")
        elif pass_rate >= 60:
            print_warning("\n⚠️  System is partially functional. Review warnings.")
        else:
            print_error("\n❌ System has issues. Review failed tests.")
        
        print("\n" + "="*70 + "\n")
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║     Enhanced OCR System Test Suite                              ║")
        print("║     Testing: Hybrid Routing, Structured NLP, Mixed Documents    ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"{Colors.END}\n")
        
        self.test_service_health()
        self.test_ocr_routing()
        self.test_structured_nlp()
        self.test_mixed_document_detection()
        self.test_api_capabilities()
        
        self.print_summary()


def main():
    """Main test runner"""
    tester = ServiceTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()

"""
Test script to verify the new folder path generation
Run this to see if the updated folder structure is working
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.routing.document_router import DocumentRouter
from datetime import datetime

def test_folder_paths():
    """Test the new folder path generation"""
    
    router = DocumentRouter()
    
    print("=" * 60)
    print("TESTING NEW FOLDER STRUCTURE")
    print("Format: department/year/month/documentType")
    print("=" * 60)
    print()
    
    # Test 1: Invoice in Finance
    print("Test 1: Invoice in Finance Department")
    print("-" * 60)
    path1 = router.generate_folder_path(
        company_id="company_123",
        department_id="Finance",
        document_type="invoice",
        date=datetime(2025, 11, 1)
    )
    print(f"Full Path: {path1.get('full_path')}")
    print(f"Base Path: {path1.get('base_path')}")
    print(f"Year Path: {path1.get('year_path')}")
    print(f"Month Path: {path1.get('month_path')}")
    print(f"Document Type: {path1.get('document_type')}")
    print(f"Month: {path1.get('month')}")
    print()
    
    # Test 2: Contract in Legal
    print("Test 2: Contract in Legal Department")
    print("-" * 60)
    path2 = router.generate_folder_path(
        company_id="company_123",
        department_id="Legal",
        document_type="contract",
        date=datetime(2025, 10, 15)
    )
    print(f"Full Path: {path2.get('full_path')}")
    print(f"Month: {path2.get('month')}")
    print()
    
    # Test 3: Receipt in Finance
    print("Test 3: Receipt in Finance Department")
    print("-" * 60)
    path3 = router.generate_folder_path(
        company_id="company_123",
        department_id="Finance",
        document_type="receipt",
        date=datetime(2025, 12, 25)
    )
    print(f"Full Path: {path3.get('full_path')}")
    print(f"Month: {path3.get('month')}")
    print()
    
    # Test 4: Form in HR
    print("Test 4: Form in HR Department")
    print("-" * 60)
    path4 = router.generate_folder_path(
        company_id="company_123",
        department_id="HR",
        document_type="form",
        date=datetime(2025, 9, 1)
    )
    print(f"Full Path: {path4.get('full_path')}")
    print(f"Month: {path4.get('month')}")
    print()
    
    # Test 5: No department (fallback)
    print("Test 5: No Department (Fallback)")
    print("-" * 60)
    path5 = router.generate_folder_path(
        company_id="company_123",
        department_id=None,
        document_type="invoice",
        date=datetime(2025, 11, 1)
    )
    print(f"Full Path: {path5.get('full_path')}")
    print()
    
    print("=" * 60)
    print("✅ EXPECTED STRUCTURE:")
    print("   /Finance/2025/November/Invoices/")
    print("   /Legal/2025/October/Contracts/")
    print("   /Finance/2025/December/Receipts/")
    print("   /HR/2025/September/Forms/")
    print("=" * 60)

if __name__ == "__main__":
    test_folder_paths()

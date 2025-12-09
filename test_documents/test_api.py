"""Test the API with the test invoice"""
import requests
import json
import os
from bson import ObjectId

# Test file
pdf_path = os.path.join(os.path.dirname(__file__), "test_invoice_with_signature.pdf")
print(f"Testing with: {pdf_path}")
print(f"File exists: {os.path.exists(pdf_path)}")

# API endpoint
url = "http://127.0.0.1:9000/api/v1/process"

# The API expects 'request' as a nested object with valid ObjectId
doc_id = str(ObjectId())  # Generate valid MongoDB ObjectId
payload = {
    "request": {
        "doc_id": doc_id,
        "pdf_file_path": pdf_path
    },
    "config_override": None
}

print(f"\nSending request to AI service...")
print(f"Doc ID: {doc_id}")
response = requests.post(url, json=payload)

print(f"\nStatus: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")
    exit(1)
result = response.json()
print(f"Response: {json.dumps(result, indent=2, default=str)}")

# Now poll for completion
import time
status_url = f"http://127.0.0.1:9000/api/v1/documents/{doc_id}/status"
print(f"\nPolling for status at: {status_url}")

for attempt in range(60):  # Wait up to 60 seconds
    time.sleep(2)
    status_resp = requests.get(status_url)
    if status_resp.status_code == 200:
        status_data = status_resp.json()
        print(f"  Attempt {attempt+1}: {status_data.get('status')}")
        if status_data.get('status') in ['COMPLETED', 'FAILED']:
            print(f"\nFinal status: {status_data.get('status')}")
            if status_data.get('error'):
                print(f"Error: {status_data.get('error')}")
            break
    else:
        print(f"  Attempt {attempt+1}: HTTP {status_resp.status_code}")

# Get full results
results_url = f"http://127.0.0.1:9000/api/v1/documents/{doc_id}"
print(f"\nFetching full results from: {results_url}")
results_resp = requests.get(results_url)

if results_resp.status_code != 200:
    print(f"Error fetching results: {results_resp.text}")
    exit(1)
    
doc_data = results_resp.json()

# Check tables
print("\n=== TABLE EXTRACTION ===")
processed = doc_data.get('processed_data', {})
if isinstance(processed, list):
    pages = processed
else:
    pages = processed.get('pages', [])
    
for i, page in enumerate(pages):
    tables = page.get('tables', [])
    print(f"\nPage {i+1}: {len(tables)} tables")
    for j, table in enumerate(tables):
        html = table.get('html', '')
        rows = table.get('rows', [])
        print(f"  Table {j+1}:")
        print(f"    HTML length: {len(html)}")
        print(f"    Rows: {len(rows)}")
        if html:
            print(f"    HTML preview: {html[:300]}...")

# Check signatures
print("\n=== SIGNATURE DETECTION ===")
for i, page in enumerate(pages):
    sig = page.get('signature', {})
    print(f"\nPage {i+1}:")
    print(f"  Detected: {sig.get('detected', False)}")
    print(f"  Boxes: {len(sig.get('boxes', []))}")
    print(f"  Text: {sig.get('text', 'N/A')[:50] if sig.get('text') else 'N/A'}...")
    print(f"  Has image: {'Yes' if sig.get('image') else 'No'}")
    if sig.get('boxes'):
        for k, box in enumerate(sig.get('boxes', [])):
            print(f"    Box {k}: {box}")

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pymongo import MongoClient
from config.settings import MONGO_URL, DATABASE_NAME

def main():
    client = MongoClient(MONGO_URL)
    db = client[DATABASE_NAME]
    
    # Get the most recent processed document
    doc = db.documents.find_one({}, sort=[('processed_at', -1)])
    if not doc:
        print('No documents found')
        return
    
    print('=== DOCUMENT INFO ===')
    print('ID:', doc.get('_id'))
    print('Filename:', doc.get('filename'))
    print('Processed at:', doc.get('processed_at'))
    print('Doc type:', doc.get('docType'))
    print('Total pages:', doc.get('totalPages'))
    print()
    
    # Get processed_data
    pd_list = doc.get('processed_data', [])
    if not pd_list:
        print('No processed_data found')
        return
    
    p = pd_list[0]
    
    print('=== CLASSIFICATION ===')
    cls = p.get('classification', {})
    print('Label:', cls.get('label'))
    print('Score:', cls.get('score'))
    print('Method:', cls.get('method'))
    reasoning = cls.get('reasoning', '')
    if reasoning:
        print('Reasoning:', reasoning[:400])
    print()
    
    print('=== EXTRACTED FIELDS ===')
    ef = p.get('extracted_fields', {})
    for k, v in ef.items():
        val = str(v)[:200]
        print(f'  {k}: {val}')
    print()
    
    print('=== ENTITIES ===')
    ent = p.get('entities', {})
    for k, v in ent.items():
        if v:
            print(f'  {k}: {v}')
    print()
    
    print('=== TABLES ===')
    tables = p.get('tables', [])
    print('Table count:', p.get('table_count', 0))
    for i, t in enumerate(tables):
        headers = t.get('headers', [])
        rows = t.get('rows', [])
        print(f'  Table {i}: rows={len(rows)}, headers={headers}')
        for j, r in enumerate(rows[:6]):
            print(f'    Row {j}: {r}')
        if len(rows) > 6:
            print(f'    ... and {len(rows)-6} more rows')
    print()
    
    print('=== SUMMARY ===')
    summary = p.get('summary', '')
    if summary:
        print(summary[:500])
    print()
    
    print('=== OCR TEXT (first 2000 chars) ===')
    text = p.get('text', '')
    print(text[:2000])
    print()
    print(f'--- Total OCR text length: {len(text)} chars ---')
    print()
    
    print('=== LAYOUT REGIONS ===')
    lr = p.get('layout_regions', [])
    print('Total regions:', len(lr))
    for r in lr[:25]:
        cls_name = r.get('class', '')
        box = r.get('box', {})
        txt = r.get('text', '')[:100]
        x = box.get('x', 0)
        y = box.get('y', 0)
        w = box.get('w', 0)
        h = box.get('h', 0)
        print(f'  [{cls_name}] box=({x:.0f},{y:.0f},{w:.0f},{h:.0f}) text={txt}')

main()

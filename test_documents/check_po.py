import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pymongo import MongoClient
from config.settings import MONGO_URL, DATABASE_NAME

def main():
    client = MongoClient(MONGO_URL)
    db = client[DATABASE_NAME]
    
    # Get the most recent purchase order document
    doc_id = '69b65f6ac38006362f000526'  # 2026-01-13_document.pdf - purchase order
    from bson import ObjectId
    doc = db.documents.find_one({'_id': ObjectId(doc_id)})
    if not doc:
        print('Document not found')
        return
    
    print('=== DOCUMENT INFO ===')
    print('ID:', doc.get('_id'))
    print('Filename:', doc.get('filename'))
    print('Doc type:', doc.get('docType'))
    print('File size:', doc.get('fileSize'))
    print('Total pages:', doc.get('totalPages'))
    print()
    
    pd_list = doc.get('processed_data', [])
    if not pd_list:
        print('No processed_data found')
        return
    
    for page_idx, p in enumerate(pd_list):
        print(f'========== PAGE {page_idx} ==========')
        
        print('--- CLASSIFICATION ---')
        cls = p.get('classification', {})
        print('Label:', cls.get('label'))
        print('Score:', cls.get('score'))
        print('Method:', cls.get('method'))
        reasoning = cls.get('reasoning', '')
        if reasoning:
            print('Reasoning:', reasoning[:500])
        print()
        
        print('--- EXTRACTED FIELDS ---')
        ef = p.get('extracted_fields', {})
        for k, v in ef.items():
            val = str(v)[:300]
            print(f'  {k}: {val}')
        print()
        
        print('--- ENTITIES ---')
        ent = p.get('entities', {})
        for k, v in ent.items():
            if v:
                print(f'  {k}: {v}')
        print()
        
        print('--- TABLES ---')
        tables = p.get('tables', [])
        print('Table count:', p.get('table_count', 0))
        for i, t in enumerate(tables):
            headers = t.get('headers', [])
            rows = t.get('rows', [])
            print(f'  Table {i}: rows={len(rows)}, headers={headers}')
            for j, r in enumerate(rows[:8]):
                print(f'    Row {j}: {r}')
            if len(rows) > 8:
                print(f'    ... and {len(rows)-8} more rows')
        print()
        
        print('--- SUMMARY ---')
        summary = p.get('summary', '')
        if summary:
            print(summary[:600])
        print()
        
        print('--- SIGNATURE ---')
        print('Signature detected:', p.get('signature_detected'))
        print('Signature text:', p.get('signature_text'))
        print('Signature confidence:', p.get('signature_confidence'))
        print()
        
        print('--- OCR TEXT (first 3000 chars) ---')
        text = p.get('text', '')
        print(text[:3000])
        print(f'--- Total OCR text length: {len(text)} chars ---')
        print()
        
        print('--- LAYOUT REGIONS ---')
        lr = p.get('layout_regions', [])
        print('Total regions:', len(lr))
        for r in lr[:30]:
            cls_name = r.get('class', '')
            box = r.get('box', {})
            txt = r.get('text', '')[:120]
            x = box.get('x', 0)
            y = box.get('y', 0)
            w = box.get('w', 0)
            h = box.get('h', 0)
            print(f'  [{cls_name}] box=({x:.0f},{y:.0f},{w:.0f},{h:.0f}) text={txt}')
        print()

main()

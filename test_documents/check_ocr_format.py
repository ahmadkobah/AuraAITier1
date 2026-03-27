from paddleocr import PaddleOCR
import numpy as np

ocr = PaddleOCR(lang='en')
# Create test with some text - use a real simple image
img = np.ones((200, 600, 3), dtype=np.uint8) * 255
# Draw some basic black rectangles as fake text
img[30:50, 50:200, :] = 0
img[70:90, 50:300, :] = 0
img[30:50, 350:550, :] = 0
img[70:90, 350:500, :] = 0

result = ocr.ocr(img)
if result and result[0]:
    d = result[0]
    if isinstance(d, dict):
        print('Result is dict with keys:', list(d.keys()))
        for k, v in d.items():
            if isinstance(v, (list, np.ndarray)):
                arr = np.array(v) if not isinstance(v, np.ndarray) else v
                s = arr.shape if hasattr(arr, 'shape') else 'N/A'
                print('  %s: type=%s, len=%d, shape=%s' % (k, type(v).__name__, len(v), s))
                if len(v) > 0:
                    print('    first element:', type(v[0]).__name__, '=', str(v[0])[:200])
            else:
                print('  %s: %s = %s' % (k, type(v).__name__, str(v)[:200]))
    else:
        print('Type:', type(d))
        if isinstance(d, list) and len(d) > 0:
            print('First element:', d[0])
else:
    print('No OCR result or empty')
    # Try predict method
    try:
        result2 = ocr.predict(img)
        print('predict result:', type(result2))
        if isinstance(result2, dict):
            print('predict keys:', list(result2.keys()))
        elif isinstance(result2, (list, tuple)) and len(result2) > 0:
            r = result2[0]
            if isinstance(r, dict):
                print('predict[0] keys:', list(r.keys()))
                for k, v in r.items():
                    if isinstance(v, (list, np.ndarray)):
                        arr = np.array(v) if not isinstance(v, np.ndarray) else v
                        s = arr.shape if hasattr(arr, 'shape') else 'N/A'
                        print('  %s: type=%s, len=%d, shape=%s' % (k, type(v).__name__, len(v), s))
                        if len(v) > 0 and len(v) <= 5:
                            for i, item in enumerate(v):
                                print('    [%d]: %s' % (i, str(item)[:200]))
                    else:
                        print('  %s: %s = %s' % (k, type(v).__name__, str(v)[:200]))
    except Exception as e:
        print('predict failed:', e)

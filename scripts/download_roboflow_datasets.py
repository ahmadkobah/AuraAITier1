"""
Download the 3 Roboflow datasets for signature, stamp, and handwriting detection.
Downloads in YOLOv8 format to models/yolo/downloads/
"""
import os
from roboflow import Roboflow

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "yolo", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Initialize Roboflow (public datasets don't need a real API key)
rf = Roboflow(api_key="public")

# 1. Signature Detection - minaehyeon (7,690 images)
print("=" * 60)
print("Downloading: Signature Detection (minaehyeon)")
print("=" * 60)
try:
    project = rf.workspace("minaehyeon").project("signature-detection-yj1a4")
    versions = project.versions()
    if versions:
        latest = versions[0]
        print(f"  Version: {latest.version}")
        dataset = latest.download("yolov8", location=os.path.join(DOWNLOAD_DIR, "signature"))
        print(f"  Downloaded to: {os.path.join(DOWNLOAD_DIR, 'signature')}")
    else:
        print("  No versions available, trying version 1...")
        dataset = project.version(1).download("yolov8", location=os.path.join(DOWNLOAD_DIR, "signature"))
except Exception as e:
    print(f"  Error: {e}")
    print("  Trying alternative: ICFAI signature detection (5,560 images)...")
    try:
        project = rf.workspace("icfai-zxp7l").project("signature-detection-b5ydm")
        versions = project.versions()
        if versions:
            latest = versions[0]
            dataset = latest.download("yolov8", location=os.path.join(DOWNLOAD_DIR, "signature"))
        else:
            dataset = project.version(1).download("yolov8", location=os.path.join(DOWNLOAD_DIR, "signature"))
        print(f"  Downloaded to: {os.path.join(DOWNLOAD_DIR, 'signature')}")
    except Exception as e2:
        print(f"  Error with alternative: {e2}")

# 2. Stamp Detection - Shujing Liang (2,340 images)
print("\n" + "=" * 60)
print("Downloading: Stamp Detection (Shujing Liang)")
print("=" * 60)
try:
    project = rf.workspace("shujing-liang").project("stamp-detection-f3yka")
    versions = project.versions()
    if versions:
        latest = versions[0]
        print(f"  Version: {latest.version}")
        dataset = latest.download("yolov8", location=os.path.join(DOWNLOAD_DIR, "stamp"))
        print(f"  Downloaded to: {os.path.join(DOWNLOAD_DIR, 'stamp')}")
    else:
        dataset = project.version(1).download("yolov8", location=os.path.join(DOWNLOAD_DIR, "stamp"))
except Exception as e:
    print(f"  Error: {e}")
    print("  Trying alternative: Stampa stamp detection (2,100 images)...")
    try:
        project = rf.workspace("stampa").project("stamp-detection-4jhgg")
        versions = project.versions()
        if versions:
            latest = versions[0]
            dataset = latest.download("yolov8", location=os.path.join(DOWNLOAD_DIR, "stamp"))
        else:
            dataset = project.version(1).download("yolov8", location=os.path.join(DOWNLOAD_DIR, "stamp"))
        print(f"  Downloaded to: {os.path.join(DOWNLOAD_DIR, 'stamp')}")
    except Exception as e2:
        print(f"  Error with alternative: {e2}")

# 3. Handwriting Detection - mohd (1,870 images)
print("\n" + "=" * 60)
print("Downloading: Handwriting Detection (mohd)")
print("=" * 60)
try:
    project = rf.workspace("mohd").project("handwriting-l6jnt")
    versions = project.versions()
    if versions:
        latest = versions[0]
        print(f"  Version: {latest.version}")
        dataset = latest.download("yolov8", location=os.path.join(DOWNLOAD_DIR, "handwriting"))
        print(f"  Downloaded to: {os.path.join(DOWNLOAD_DIR, 'handwriting')}")
    else:
        dataset = project.version(1).download("yolov8", location=os.path.join(DOWNLOAD_DIR, "handwriting"))
except Exception as e:
    print(f"  Error: {e}")
    print("  Trying alternative: Hand Writing Detection (1,000 images)...")
    try:
        project = rf.workspace("hand-writing-detection").project("handwriting-detection-mi4aa")
        versions = project.versions()
        if versions:
            latest = versions[0]
            dataset = latest.download("yolov8", location=os.path.join(DOWNLOAD_DIR, "handwriting"))
        else:
            dataset = project.version(1).download("yolov8", location=os.path.join(DOWNLOAD_DIR, "handwriting"))
        print(f"  Downloaded to: {os.path.join(DOWNLOAD_DIR, 'handwriting')}")
    except Exception as e2:
        print(f"  Error with alternative: {e2}")

print("\n" + "=" * 60)
print("DOWNLOAD COMPLETE")
print("=" * 60)
# List what we got
for name in ["signature", "stamp", "handwriting"]:
    path = os.path.join(DOWNLOAD_DIR, name)
    if os.path.isdir(path):
        total = sum(len(files) for _, _, files in os.walk(path))
        print(f"  {name}: {total} files")
    else:
        print(f"  {name}: NOT DOWNLOADED")

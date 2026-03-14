"""
Download large datasets for signature, stamp, and handwriting from Roboflow Universe.
Uses exact workspace/project slugs found from Universe search pages.
Then merges everything and balances the dataset.
"""
import os
import sys
import shutil
import random
from pathlib import Path
from collections import defaultdict

API_KEY = os.environ.get("ROBOFLOW_API_KEY", "D6CSnT6JnSXemNcmySCZ")
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "models" / "yolo" / "data"
DOWNLOADS = PROJECT_ROOT / "models" / "yolo" / "downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

# ============================================================
# STEP 1: Download datasets with EXACT slugs from Universe
# ============================================================

# Top signature datasets (sorted by size)
SIGNATURE_DATASETS = [
    ("minaehyeon", "signature-detection-yj1a4", 1, "sig_minaehyeon"),       # 7.69k
    ("icfai-zxp7l", "signature-detection-b5ydm", 1, "sig_icfai"),           # 5.56k
    ("mri-iyhg7", "signature-detection-2uyoc", 1, "sig_mri"),               # 5.43k
    ("glcvcapstone", "signature-detection-1geyl", 1, "sig_glcv"),           # 2.32k
    ("amruth", "signature-detection-qky9p", 1, "sig_amruth"),               # 2.23k
    ("celldetection-npo3o", "signature-detection-em7qc", 1, "sig_celldet"), # 1.86k
    ("emirhan-zxhfc", "signature-detection-dxu9n", 1, "sig_emirhan"),       # 1.44k
    ("agastyas-workspace", "signature-detection-rzqoe", 1, "sig_agastya"),  # 1.29k
    ("tech-ysdkk", "signature-detection-hlx8j", 1, "sig_tech"),            # 1.24k
]

# Top stamp/seal datasets
STAMP_DATASETS = [
    ("class-cemy0", "stamp-wnh42", 1, "stp_class"),           # 2.29k (Non_Stamp/Stamp)
    ("stampa", "stamp-detection-4jhgg", 1, "stp_stampa"),     # 2.1k (signature, stamp)
    ("yolo12-kufr0", "seal-detection-nyqwf", 1, "stp_yolo12"),# 1.25k
    ("stamp-ekzu0", "stamp-gj1og", 1, "stp_ekzu0"),           # 961
    ("cvic", "seal-jgwgd", 1, "stp_cvic"),                    # 913 (document seals)
    ("seal-zxiuy", "seal-u2gew", 1, "stp_seal"),              # 892
    ("rajuk", "seal-detection-xvhk7", 1, "stp_rajuk"),        # 883
    ("1-pxuwk", "stamp-9l8nn", 1, "stp_1pxuwk"),              # 547
]

# Top handwriting datasets (focusing on region detection, not character recognition)
HANDWRITING_DATASETS = [
    ("hand-writing-detection", "handwriting-detection-mi4aa", 1, "hw_handdet"),  # 1k
    ("alphabet-map", "handwriting-detection-jgfhy", 1, "hw_alphabet"),           # 2.59k
    ("computer-vision-project-xu4um", "handwriting-detection-fgs65", 1, "hw_cvproj"), # 781
    ("handwriting-detection-zfowd", "handwriting-detection-eoxpj", 1, "hw_zfowd"),    # 361
    ("pratyush-garg-jdv57", "doctor-s-handwriting", 1, "hw_doctor"),                  # 637
    ("fyp-xrrtb", "handwriting-jlzlb", 1, "hw_fyp"),                                 # 498
    ("new-workspace-kemzl", "letters-handwriting", 1, "hw_letters"),                   # 4.04k
]


def download_dataset(workspace, project, version, name):
    """Download a single dataset from Roboflow Universe."""
    target = DOWNLOADS / name
    
    # Check if already downloaded
    if target.exists():
        imgs = sum(1 for _ in target.rglob("*.jpg")) + sum(1 for _ in target.rglob("*.png"))
        if imgs > 0:
            print(f"  SKIP (exists): {name} - {imgs} images")
            return target, imgs
    
    try:
        from roboflow import Roboflow
        rf = Roboflow(api_key=API_KEY)
        proj = rf.workspace(workspace).project(project)
        ver = proj.version(version)
        ver.download("yolov8", location=str(target))
        imgs = sum(1 for _ in target.rglob("*.jpg")) + sum(1 for _ in target.rglob("*.png"))
        print(f"  OK: {workspace}/{project} v{version} -> {imgs} images")
        return target, imgs
    except Exception as e:
        err = str(e)[:150]
        print(f"  FAIL: {workspace}/{project} v{version} -> {err}")
        return None, 0


def count_annotations_in_dir(label_dir):
    """Count annotation lines in all label files in a directory."""
    count = 0
    if not label_dir.exists():
        return 0
    for f in label_dir.glob("*.txt"):
        if f.name == "classes.txt":
            continue
        with open(f) as fh:
            count += sum(1 for line in fh if line.strip())
    return count


def merge_dataset(src_dir, target_class_id, prefix, class_name):
    """Merge a downloaded dataset into our main data directory."""
    import yaml
    
    if src_dir is None or not src_dir.exists():
        return 0, 0
    
    # Find data.yaml
    data_yaml = None
    for root, dirs, files in os.walk(src_dir):
        if "data.yaml" in files:
            data_yaml = Path(root) / "data.yaml"
            break
    
    if not data_yaml:
        print(f"    No data.yaml in {src_dir}")
        return 0, 0
    
    base_dir = data_yaml.parent
    with open(data_yaml, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    names = config.get("names", {})
    if isinstance(names, list):
        names = {i: n for i, n in enumerate(names)}
    
    # Map ALL source classes to our target class
    class_remap = {i: target_class_id for i in names}
    
    total_images = 0
    total_anns = 0
    
    for split_name, split_aliases in [("train", ["train", "training"]), ("val", ["valid", "val", "test"])]:
        for alias in split_aliases:
            src_img = base_dir / alias / "images"
            src_lbl = base_dir / alias / "labels"
            if src_img.is_dir() and src_lbl.is_dir():
                dst_img = DATA_DIR / "images" / split_name
                dst_lbl = DATA_DIR / "labels" / split_name
                dst_img.mkdir(parents=True, exist_ok=True)
                dst_lbl.mkdir(parents=True, exist_ok=True)
                
                copied = 0
                anns = 0
                for img_file in src_img.iterdir():
                    if img_file.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
                        continue
                    
                    label_file = src_lbl / (img_file.stem + ".txt")
                    if not label_file.exists():
                        continue
                    
                    # Remap labels
                    new_lines = []
                    with open(label_file) as fh:
                        for line in fh:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                src_cls = int(parts[0])
                                if src_cls in class_remap:
                                    parts[0] = str(class_remap[src_cls])
                                    new_lines.append(" ".join(parts))
                                    anns += 1
                    
                    if not new_lines:
                        continue
                    
                    new_name = f"{prefix}_{img_file.stem}"
                    dst_i = dst_img / (new_name + img_file.suffix)
                    dst_l = dst_lbl / (new_name + ".txt")
                    
                    if dst_i.exists():
                        continue
                    
                    shutil.copy2(img_file, dst_i)
                    with open(dst_l, 'w') as fh:
                        fh.write("\n".join(new_lines) + "\n")
                    copied += 1
                
                total_images += copied
                total_anns += anns
                break
    
    return total_images, total_anns


def count_class_distribution():
    """Count annotations per class across the full dataset."""
    dist = defaultdict(int)
    for split in ["train", "val"]:
        lbl_dir = DATA_DIR / "labels" / split
        if not lbl_dir.exists():
            continue
        for f in lbl_dir.glob("*.txt"):
            with open(f) as fh:
                for line in fh:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        dist[cls_id] += 1
    return dist


def balance_dataset(target_per_class=15000):
    """
    Balance the dataset by:
    1. Downsampling over-represented classes (remove images that ONLY have those classes)
    2. Oversampling under-represented classes (duplicate images)
    
    Target: ~15K annotations per class for the balanced set.
    """
    CLASS_NAMES = {
        0: "text_block", 1: "table", 2: "figure", 3: "signature",
        4: "stamp", 5: "handwriting_region", 6: "header", 7: "footer"
    }
    
    print("\n" + "=" * 60)
    print("BALANCING DATASET")
    print("=" * 60)
    
    for split in ["train", "val"]:
        img_dir = DATA_DIR / "images" / split
        lbl_dir = DATA_DIR / "labels" / split
        
        if not lbl_dir.exists():
            continue
        
        # Build index: which classes are in each label file
        file_classes = {}  # filename -> set of class IDs
        file_class_counts = {}  # filename -> {class_id: count}
        
        for f in lbl_dir.glob("*.txt"):
            classes = set()
            counts = defaultdict(int)
            with open(f) as fh:
                for line in fh:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls = int(parts[0])
                        classes.add(cls)
                        counts[cls] += 1
            if classes:
                file_classes[f.stem] = classes
                file_class_counts[f.stem] = dict(counts)
        
        # Count current annotations per class
        class_anns = defaultdict(int)
        for stem, counts in file_class_counts.items():
            for cls, cnt in counts.items():
                class_anns[cls] += cnt
        
        print(f"\n  {split.upper()} - Current distribution:")
        for cls_id in sorted(class_anns.keys()):
            name = CLASS_NAMES.get(cls_id, f"unknown_{cls_id}")
            print(f"    {cls_id}: {name} = {class_anns[cls_id]:,} annotations")
        
        # === DOWNSAMPLING over-represented classes ===
        # For header (280K) and footer (80K), remove SOME images that only contain those
        over_represented = {cls_id for cls_id, count in class_anns.items() 
                           if count > target_per_class * 2}
        
        if over_represented and split == "train":
            # Find images that ONLY have over-represented classes
            removable = []
            for stem, classes in file_classes.items():
                # Only remove if ALL classes in this image are over-represented
                if classes.issubset(over_represented):
                    removable.append(stem)
            
            random.seed(42)
            random.shuffle(removable)
            
            # Calculate how many to remove
            # We want to bring the biggest class down to ~target_per_class
            max_class = max(class_anns.values())
            removal_ratio = max(0, 1 - (target_per_class * 2 / max_class))
            to_remove = int(len(removable) * removal_ratio)
            
            if to_remove > 0:
                print(f"\n    Downsampling: removing {to_remove} images (only over-represented classes)")
                removed = 0
                for stem in removable[:to_remove]:
                    img_candidates = list(img_dir.glob(f"{stem}.*"))
                    lbl_file = lbl_dir / f"{stem}.txt"
                    
                    # Update counts
                    if stem in file_class_counts:
                        for cls, cnt in file_class_counts[stem].items():
                            class_anns[cls] -= cnt
                    
                    for img_f in img_candidates:
                        img_f.unlink()
                    if lbl_file.exists():
                        lbl_file.unlink()
                    removed += 1
                
                print(f"    Removed {removed} images")
        
        # === OVERSAMPLING under-represented classes ===
        under_represented = {cls_id for cls_id, count in class_anns.items() 
                            if count < target_per_class and cls_id in (3, 4, 5)}
        
        if under_represented and split == "train":
            for target_cls in sorted(under_represented):
                current = class_anns[target_cls]
                if current == 0:
                    continue
                
                # Find all files containing this class
                source_files = [stem for stem, classes in file_classes.items()
                               if target_cls in classes]
                
                if not source_files:
                    continue
                
                # How many copies needed?
                multiplier = min(target_per_class // current, 20)  # Cap at 20x
                if multiplier <= 1:
                    continue
                
                name = CLASS_NAMES.get(target_cls, f"cls_{target_cls}")
                print(f"\n    Oversampling {name}: {current} -> ~{current * multiplier} (x{multiplier})")
                
                random.seed(42)
                added = 0
                for copy_idx in range(1, multiplier):
                    for stem in source_files:
                        new_stem = f"aug{copy_idx}_{stem}"
                        
                        # Find source image
                        src_img = None
                        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                            candidate = img_dir / f"{stem}{ext}"
                            if candidate.exists():
                                src_img = candidate
                                break
                        
                        src_lbl = lbl_dir / f"{stem}.txt"
                        if not src_img or not src_lbl.exists():
                            continue
                        
                        dst_img = img_dir / f"{new_stem}{src_img.suffix}"
                        dst_lbl = lbl_dir / f"{new_stem}.txt"
                        
                        if not dst_img.exists():
                            shutil.copy2(src_img, dst_img)
                            shutil.copy2(src_lbl, dst_lbl)
                            added += 1
                
                class_anns[target_cls] = current * multiplier
                print(f"    Added {added} augmented copies")
        
        # Final count
        print(f"\n  {split.upper()} - After balancing:")
        for cls_id in sorted(class_anns.keys()):
            name = CLASS_NAMES.get(cls_id, f"unknown_{cls_id}")
            print(f"    {cls_id}: {name} = {class_anns[cls_id]:,} annotations")


def main():
    # ============================================================
    # DOWNLOAD PHASE
    # ============================================================
    
    print("=" * 60)
    print("PHASE 1: DOWNLOADING SIGNATURE DATASETS")
    print("=" * 60)
    sig_total = 0
    sig_dirs = []
    for ws, proj, ver, name in SIGNATURE_DATASETS:
        path, count = download_dataset(ws, proj, ver, name)
        if path:
            sig_dirs.append((path, name))
            sig_total += count
        if sig_total >= 8000:  # enough signatures
            break
    
    print(f"\nSignature total: {sig_total} images downloaded")
    
    print("\n" + "=" * 60)
    print("PHASE 2: DOWNLOADING STAMP DATASETS")
    print("=" * 60)
    stp_total = 0
    stp_dirs = []
    for ws, proj, ver, name in STAMP_DATASETS:
        path, count = download_dataset(ws, proj, ver, name)
        if path:
            stp_dirs.append((path, name))
            stp_total += count
        if stp_total >= 5000:
            break
    
    print(f"\nStamp total: {stp_total} images downloaded")
    
    print("\n" + "=" * 60)
    print("PHASE 3: DOWNLOADING HANDWRITING DATASETS")
    print("=" * 60)
    hw_total = 0
    hw_dirs = []
    for ws, proj, ver, name in HANDWRITING_DATASETS:
        path, count = download_dataset(ws, proj, ver, name)
        if path:
            hw_dirs.append((path, name))
            hw_total += count
        if hw_total >= 5000:
            break
    
    print(f"\nHandwriting total: {hw_total} images downloaded")
    
    # ============================================================
    # MERGE PHASE
    # ============================================================
    print("\n" + "=" * 60)
    print("PHASE 4: MERGING INTO MAIN DATASET")
    print("=" * 60)
    
    # Merge signatures (class 3)
    sig_imgs = sig_anns = 0
    for path, name in sig_dirs:
        prefix = name
        imgs, anns = merge_dataset(path, 3, prefix, "signature")
        sig_imgs += imgs
        sig_anns += anns
    print(f"  Signatures merged: {sig_imgs} images, {sig_anns} annotations")
    
    # Merge stamps (class 4)
    stp_imgs = stp_anns = 0
    for path, name in stp_dirs:
        prefix = name
        imgs, anns = merge_dataset(path, 4, prefix, "stamp")
        stp_imgs += imgs
        stp_anns += anns
    print(f"  Stamps merged: {stp_imgs} images, {stp_anns} annotations")
    
    # Merge handwriting (class 5)
    hw_imgs = hw_anns = 0
    for path, name in hw_dirs:
        prefix = name
        imgs, anns = merge_dataset(path, 5, prefix, "handwriting_region")
        hw_imgs += imgs
        hw_anns += anns
    print(f"  Handwriting merged: {hw_imgs} images, {hw_anns} annotations")
    
    # ============================================================
    # BALANCE PHASE
    # ============================================================
    print("\n" + "=" * 60)
    print("PHASE 5: CURRENT DISTRIBUTION")
    print("=" * 60)
    
    CLASS_NAMES = {
        0: "text_block", 1: "table", 2: "figure", 3: "signature",
        4: "stamp", 5: "handwriting_region", 6: "header", 7: "footer"
    }
    
    dist = count_class_distribution()
    for cls_id in sorted(dist.keys()):
        name = CLASS_NAMES.get(cls_id, f"unknown_{cls_id}")
        print(f"  {cls_id}: {name} = {dist[cls_id]:,} annotations")
    
    # Count images
    for split in ["train", "val"]:
        img_dir = DATA_DIR / "images" / split
        if img_dir.exists():
            count = len(list(img_dir.iterdir()))
            print(f"  {split}: {count} images")
    
    # Balance
    balance_dataset(target_per_class=15000)
    
    # Final distribution
    print("\n" + "=" * 60)
    print("FINAL DATASET SUMMARY")
    print("=" * 60)
    
    dist = count_class_distribution()
    for cls_id in sorted(dist.keys()):
        name = CLASS_NAMES.get(cls_id, f"unknown_{cls_id}")
        print(f"  {cls_id}: {name} = {dist[cls_id]:,} annotations")
    
    for split in ["train", "val"]:
        img_dir = DATA_DIR / "images" / split
        if img_dir.exists():
            count = len(list(img_dir.iterdir()))
            print(f"  {split}: {count} images")


if __name__ == "__main__":
    main()

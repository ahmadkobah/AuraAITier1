"""
Merge Roboflow YOLO exports into the existing DocLayNet dataset.

Usage:
    python scripts/merge_roboflow_datasets.py \
        --signature  path/to/signature-dataset.zip \
        --stamp      path/to/stamp-dataset.zip \
        --handwriting path/to/handwriting-dataset.zip

Each ZIP should be a Roboflow YOLOv8 export containing:
    train/images/*, train/labels/*, valid/images/*, valid/labels/*, data.yaml

The script:
  1. Extracts each ZIP to a temp directory
  2. Reads the source data.yaml to discover class names
  3. Remaps all class IDs to our 8-class scheme:
       0=text_block, 1=table, 2=figure, 3=signature, 4=stamp,
       5=handwriting_region, 6=header, 7=footer
  4. Copies images + remapped labels into models/yolo/data/{images,labels}/{train,val}/
  5. Prints a summary of added images per class
"""

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
import yaml
from pathlib import Path

# Our project's 8-class scheme
TARGET_CLASSES = {
    0: "text_block",
    1: "table",
    2: "figure",
    3: "signature",
    4: "stamp",
    5: "handwriting_region",
    6: "header",
    7: "footer",
}

# Reverse lookup: name -> target ID
TARGET_NAME_TO_ID = {v: k for k, v in TARGET_CLASSES.items()}

# Mapping of common Roboflow class name variants to our target class names
SIGNATURE_ALIASES = {
    "signature", "sign", "signatures", "handwritten_signature",
    "signature-fake", "signature-real", "signature_box",
    "0",  # many single-class Roboflow datasets use "0" as the class name
}
STAMP_ALIASES = {
    "stamp", "stamps", "seal", "seals", "stamp-seal",
    "e-stamp_seal", "materai", "stamp-materai",
    "0",
}
HANDWRITING_ALIASES = {
    "handwriting", "handwriting text", "handwritten", "hw",
    "handwriting_region", "line", "text",
    "0",
}


def find_class_mapping(source_names: dict, target_class: str) -> dict:
    """
    Build a mapping from source class IDs to the single target class ID.
    
    For single-class datasets (common on Roboflow) maps class 0 -> target.
    For multi-class datasets, tries to match by name alias.
    
    Returns: {source_id: target_id}
    """
    target_id = TARGET_NAME_TO_ID[target_class]
    
    if target_class == "signature":
        aliases = SIGNATURE_ALIASES
    elif target_class == "stamp":
        aliases = STAMP_ALIASES
    elif target_class == "handwriting_region":
        aliases = HANDWRITING_ALIASES
    else:
        aliases = {target_class}
    
    mapping = {}
    
    # Single class dataset — map everything to target
    if len(source_names) == 1:
        src_id = list(source_names.keys())[0]
        mapping[src_id] = target_id
        print(f"    Single-class dataset: '{source_names[src_id]}' (id={src_id}) -> {target_class} (id={target_id})")
        return mapping
    
    # Multi-class dataset — match by alias
    for src_id, src_name in source_names.items():
        normalized = src_name.lower().strip().replace("-", "_").replace(" ", "_")
        if normalized in {a.lower().replace("-", "_").replace(" ", "_") for a in aliases}:
            mapping[src_id] = target_id
            print(f"    Matched: '{src_name}' (id={src_id}) -> {target_class} (id={target_id})")
    
    if not mapping:
        # Fallback: if dataset has a class that contains the target word
        for src_id, src_name in source_names.items():
            if target_class.split("_")[0] in src_name.lower():
                mapping[src_id] = target_id
                print(f"    Fuzzy matched: '{src_name}' (id={src_id}) -> {target_class} (id={target_id})")
    
    if not mapping:
        print(f"    WARNING: Could not auto-map any class to '{target_class}'.")
        print(f"    Source classes: {source_names}")
        print(f"    Falling back: mapping ALL source classes -> {target_class}")
        for src_id in source_names:
            mapping[src_id] = target_id
    
    return mapping


def extract_and_find_structure(zip_path: str, temp_dir: str) -> dict:
    """Extract ZIP and find the data.yaml + image/label dirs."""
    print(f"  Extracting {os.path.basename(zip_path)}...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)
    
    # Find data.yaml (may be at root or in a subfolder)
    data_yaml = None
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            if f == "data.yaml":
                data_yaml = os.path.join(root, f)
                break
        if data_yaml:
            break
    
    if not data_yaml:
        raise FileNotFoundError(f"No data.yaml found in {zip_path}")
    
    base_dir = os.path.dirname(data_yaml)
    
    with open(data_yaml, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Parse class names
    names = config.get("names", {})
    if isinstance(names, list):
        names = {i: n for i, n in enumerate(names)}
    
    # Find image/label directories
    # Roboflow exports as: train/images, train/labels, valid/images, valid/labels
    # or sometimes: images/train, labels/train, images/val, labels/val
    structure = {"base": base_dir, "names": names, "splits": {}}
    
    for split_name, split_aliases in [("train", ["train", "training"]), ("val", ["valid", "val", "test"])]:
        for alias in split_aliases:
            img_dir = os.path.join(base_dir, alias, "images")
            lbl_dir = os.path.join(base_dir, alias, "labels")
            if os.path.isdir(img_dir) and os.path.isdir(lbl_dir):
                structure["splits"][split_name] = {"images": img_dir, "labels": lbl_dir}
                break
        
        if split_name not in structure["splits"]:
            # Try alternate structure: images/train, labels/train
            img_dir = os.path.join(base_dir, "images", split_aliases[0])
            lbl_dir = os.path.join(base_dir, "labels", split_aliases[0])
            if os.path.isdir(img_dir) and os.path.isdir(lbl_dir):
                structure["splits"][split_name] = {"images": img_dir, "labels": lbl_dir}
    
    if not structure["splits"]:
        raise FileNotFoundError(f"No train/valid splits found in {zip_path}. Directory: {os.listdir(base_dir)}")
    
    return structure


def remap_label_file(src_label: str, dst_label: str, class_mapping: dict) -> int:
    """
    Read a YOLO label file, remap class IDs, write to destination.
    Returns the number of annotations written.
    """
    annotations = 0
    lines_out = []
    
    with open(src_label, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            src_class = int(parts[0])
            if src_class in class_mapping:
                parts[0] = str(class_mapping[src_class])
                lines_out.append(" ".join(parts))
                annotations += 1
    
    if lines_out:
        os.makedirs(os.path.dirname(dst_label), exist_ok=True)
        with open(dst_label, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines_out) + "\n")
    
    return annotations


def merge_dataset(zip_path: str, target_class: str, output_base: str, prefix: str) -> dict:
    """
    Merge one Roboflow ZIP into the existing dataset.
    
    Args:
        zip_path: Path to the Roboflow YOLO export ZIP
        target_class: Our target class name (signature, stamp, handwriting_region)
        output_base: Path to models/yolo/data/
        prefix: Unique prefix to avoid filename collisions (e.g., 'sig', 'stp', 'hw')
    
    Returns: stats dict
    """
    stats = {"images": 0, "annotations": 0, "splits": {}}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        structure = extract_and_find_structure(zip_path, temp_dir)
        print(f"  Found classes: {structure['names']}")
        print(f"  Found splits: {list(structure['splits'].keys())}")
        
        class_mapping = find_class_mapping(structure["names"], target_class)
        
        if not class_mapping:
            print(f"  ERROR: No class mapping could be established. Skipping.")
            return stats
        
        for split_name, dirs in structure["splits"].items():
            img_dir = dirs["images"]
            lbl_dir = dirs["labels"]
            
            dst_img_dir = os.path.join(output_base, "images", split_name)
            dst_lbl_dir = os.path.join(output_base, "labels", split_name)
            os.makedirs(dst_img_dir, exist_ok=True)
            os.makedirs(dst_lbl_dir, exist_ok=True)
            
            split_images = 0
            split_annotations = 0
            
            img_files = [f for f in os.listdir(img_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))]
            
            for img_file in img_files:
                stem = Path(img_file).stem
                ext = Path(img_file).suffix
                label_file = stem + ".txt"
                
                src_label = os.path.join(lbl_dir, label_file)
                if not os.path.exists(src_label):
                    continue
                
                # Add prefix to avoid filename collisions with existing DocLayNet images
                new_name = f"{prefix}_{stem}"
                dst_img = os.path.join(dst_img_dir, new_name + ext)
                dst_lbl = os.path.join(dst_lbl_dir, new_name + ".txt")
                
                # Skip if already exists (idempotent)
                if os.path.exists(dst_img):
                    continue
                
                ann_count = remap_label_file(src_label, dst_lbl, class_mapping)
                if ann_count > 0:
                    shutil.copy2(os.path.join(img_dir, img_file), dst_img)
                    split_images += 1
                    split_annotations += ann_count
            
            stats["splits"][split_name] = {"images": split_images, "annotations": split_annotations}
            stats["images"] += split_images
            stats["annotations"] += split_annotations
            
            print(f"  {split_name}: {split_images} images, {split_annotations} annotations")
    
    return stats


def count_existing_dataset(output_base: str) -> dict:
    """Count existing images in the dataset."""
    counts = {}
    for split in ["train", "val"]:
        img_dir = os.path.join(output_base, "images", split)
        if os.path.isdir(img_dir):
            counts[split] = len([f for f in os.listdir(img_dir) if not f.startswith('.')])
        else:
            counts[split] = 0
    return counts


def main():
    parser = argparse.ArgumentParser(description="Merge Roboflow YOLO exports into existing DocLayNet dataset")
    parser.add_argument("--signature", type=str, help="Path to signature detection ZIP")
    parser.add_argument("--stamp", type=str, help="Path to stamp/seal detection ZIP")
    parser.add_argument("--handwriting", type=str, help="Path to handwriting detection ZIP")
    parser.add_argument("--data-dir", type=str, 
                        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "yolo", "data"),
                        help="Path to models/yolo/data/ (default: auto-detected)")
    args = parser.parse_args()
    
    if not any([args.signature, args.stamp, args.handwriting]):
        parser.error("Provide at least one of: --signature, --stamp, --handwriting")
    
    output_base = args.data_dir
    print(f"Output directory: {output_base}")
    
    # Show existing counts
    existing = count_existing_dataset(output_base)
    print(f"\nExisting dataset: {existing.get('train', 0)} train, {existing.get('val', 0)} val")
    
    total_stats = {"images": 0, "annotations": 0}
    
    datasets = [
        (args.signature, "signature", "sig"),
        (args.stamp, "stamp", "stp"),
        (args.handwriting, "handwriting_region", "hw"),
    ]
    
    for zip_path, target_class, prefix in datasets:
        if not zip_path:
            continue
        
        if not os.path.exists(zip_path):
            print(f"\nERROR: File not found: {zip_path}")
            continue
        
        print(f"\n{'='*60}")
        print(f"Merging: {target_class} from {os.path.basename(zip_path)}")
        print(f"{'='*60}")
        
        stats = merge_dataset(zip_path, target_class, output_base, prefix)
        total_stats["images"] += stats["images"]
        total_stats["annotations"] += stats["annotations"]
    
    # Final summary
    final = count_existing_dataset(output_base)
    print(f"\n{'='*60}")
    print(f"MERGE COMPLETE")
    print(f"{'='*60}")
    print(f"Added:  {total_stats['images']} images, {total_stats['annotations']} annotations")
    print(f"Before: {existing.get('train', 0)} train, {existing.get('val', 0)} val")
    print(f"After:  {final.get('train', 0)} train, {final.get('val', 0)} val")
    print(f"\nReady to retrain:")
    print(f"  python scripts/train_document_yolo.py")


if __name__ == "__main__":
    main()

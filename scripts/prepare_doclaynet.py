"""
Download and convert DocLayNet (IBM) dataset to YOLO format for document layout training.

DocLayNet: 80,863 manually annotated pages with 11 classes (CC-BY-4.0)
Source: https://huggingface.co/datasets/ds4sd/DocLayNet

This script:
  1. Downloads DocLayNet from Hugging Face (or uses a local copy)
  2. Remaps 11 DocLayNet classes → 8 project layout classes
  3. Converts COCO-format annotations → YOLO .txt format
  4. Splits into train/val folders matching data.yaml
  5. Optionally limits the dataset size (for quick experiments)

Usage:
    python scripts/prepare_doclaynet.py                    # Full dataset (~80K images)
    python scripts/prepare_doclaynet.py --limit 5000       # Quick experiment (5K images)
    python scripts/prepare_doclaynet.py --limit 2000 --val-split 0.2
    python scripts/prepare_doclaynet.py --local path/to/doclaynet  # Use local download

Output:
    models/yolo/data/
    ├── images/train/   (80% of images)
    ├── images/val/     (20% of images)
    ├── labels/train/   (YOLO .txt annotations)
    ├── labels/val/     (YOLO .txt annotations)
    └── data.yaml       (dataset config)

Requirements:
    pip install datasets Pillow tqdm
"""

import argparse
import json
import os
import random
import shutil
import sys
from pathlib import Path

# ── DocLayNet 11 classes → Project 8 classes mapping ────────────────────
# DocLayNet classes (0-10):
#   0: Caption, 1: Footnote, 2: Formula, 3: List-item, 4: Page-footer,
#   5: Page-header, 6: Picture, 7: Section-header, 8: Table, 9: Text, 10: Title
#
# Project classes (0-7):
#   0: text_block, 1: table, 2: figure, 3: signature, 4: stamp,
#   5: handwriting_region, 6: header, 7: footer

DOCLAYNET_TO_PROJECT = {
    0: 0,      # Caption → text_block
    1: 0,      # Footnote → text_block
    2: 0,      # Formula → text_block
    3: 0,      # List-item → text_block
    4: 7,      # Page-footer → footer
    5: 6,      # Page-header → header
    6: 2,      # Picture → figure
    7: 6,      # Section-header → header
    8: 1,      # Table → table
    9: 0,      # Text → text_block
    10: 6,     # Title → header
}

PROJECT_CLASSES = {
    0: 'text_block',
    1: 'table',
    2: 'figure',
    3: 'signature',
    4: 'stamp',
    5: 'handwriting_region',
    6: 'header',
    7: 'footer',
}


def coco_to_yolo(bbox, img_width, img_height):
    """Convert COCO bbox [x, y, w, h] (absolute) → YOLO [x_center, y_center, w, h] (normalized 0-1)."""
    x, y, w, h = bbox
    x_center = (x + w / 2) / img_width
    y_center = (y + h / 2) / img_height
    w_norm = w / img_width
    h_norm = h / img_height
    # Clamp to [0, 1]
    x_center = max(0.0, min(1.0, x_center))
    y_center = max(0.0, min(1.0, y_center))
    w_norm = max(0.0, min(1.0, w_norm))
    h_norm = max(0.0, min(1.0, h_norm))
    return x_center, y_center, w_norm, h_norm


def download_doclaynet(output_dir: str, limit: int = 0):
    """Download DocLayNet from Hugging Face.
    
    For small limits (<= 5000): downloads ONE parquet shard (~1GB) via huggingface_hub.
    For full dataset: uses datasets library to download all shards (~30GB).
    """
    REPO = "ds4sd/DocLayNet-v1.1"
    print(f"Downloading DocLayNet from Hugging Face ({REPO})...")
    print("  Subsequent runs use the Hugging Face cache.")

    if 0 < limit <= 5000:
        # Fast path: download just ONE parquet shard and extract samples
        print(f"  Fast mode: downloading one shard for --limit {limit}")
        try:
            from huggingface_hub import hf_hub_download, list_repo_files
            import pyarrow.parquet as pq
            from PIL import Image as PILImage
            import io

            # Find the first parquet shard filename dynamically
            all_files = list_repo_files(REPO, repo_type="dataset")
            shards = sorted([f for f in all_files if f.endswith('.parquet') and 'train' in f])
            if not shards:
                raise ValueError("No training parquet shards found in repo")

            shard_path = hf_hub_download(
                repo_id=REPO,
                filename=shards[0],
                repo_type="dataset",
            )
            print(f"  Shard downloaded: {shard_path}")

            table = pq.read_table(shard_path)
            total = min(limit, len(table))

            # Convert to list of dicts with PIL images
            samples = []
            for i in range(total):
                row = {col: table.column(col)[i].as_py() for col in table.column_names}
                # Convert image bytes to PIL Image
                img_data = row.get('image', {})
                if isinstance(img_data, dict) and 'bytes' in img_data:
                    row['image'] = PILImage.open(io.BytesIO(img_data['bytes']))
                elif isinstance(img_data, bytes):
                    row['image'] = PILImage.open(io.BytesIO(img_data))
                samples.append(row)

            print(f"  Loaded {len(samples)} samples from shard")
            return samples, len(samples)

        except Exception as e:
            print(f"  Fast download failed ({e}), falling back to datasets library...")

    # Full download
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' package required. Install with: pip install datasets")
        sys.exit(1)

    print("  Downloading full dataset (this may take a while, ~30 GB)...")
    ds = load_dataset(REPO, split="train")
    total = len(ds)
    if limit > 0:
        total = min(limit, total)
        print(f"  Limiting to {total} images (--limit {limit})")
    return ds, total


def process_hf_dataset(ds, total, output_dir, val_split):
    """Process Hugging Face dataset → YOLO format."""
    from tqdm import tqdm

    images_train = os.path.join(output_dir, 'images', 'train')
    images_val = os.path.join(output_dir, 'images', 'val')
    labels_train = os.path.join(output_dir, 'labels', 'train')
    labels_val = os.path.join(output_dir, 'labels', 'val')

    for d in [images_train, images_val, labels_train, labels_val]:
        os.makedirs(d, exist_ok=True)

    # Generate deterministic split indices
    random.seed(42)
    indices = list(range(total))
    random.shuffle(indices)
    val_count = int(total * val_split)
    val_indices = set(indices[:val_count])

    stats = {'total': 0, 'train': 0, 'val': 0, 'annotations': 0, 'skipped': 0}
    class_counts = {v: 0 for v in PROJECT_CLASSES.values()}

    print(f"\nConverting {total} images to YOLO format...")
    
    for idx in tqdm(range(total), desc="Converting"):
        try:
            sample = ds[idx]
        except (IndexError, Exception) as e:
            stats['skipped'] += 1
            continue

        # Print schema of first sample for debugging
        if idx == 0:
            print(f"  Sample keys: {list(sample.keys())}")
            for k, v in sample.items():
                if k != 'image':
                    vstr = str(v)[:120]
                    print(f"    {k}: {type(v).__name__} = {vstr}")

        image = sample.get('image')
        if image is None:
            stats['skipped'] += 1
            continue

        img_width, img_height = image.size
        if img_width < 10 or img_height < 10:
            stats['skipped'] += 1
            continue

        # Determine split
        is_val = idx in val_indices
        img_dir = images_val if is_val else images_train
        lbl_dir = labels_val if is_val else labels_train

        # Save image
        filename = f"doclaynet_{idx:06d}.png"
        img_path = os.path.join(img_dir, filename)
        
        # Resize to max 1024px longest side (consistent with training config)
        max_dim = max(img_width, img_height)
        if max_dim > 1024:
            scale = 1024 / max_dim
            new_w = int(img_width * scale)
            new_h = int(img_height * scale)
            image = image.resize((new_w, new_h))
            img_width, img_height = new_w, new_h
        
        image.save(img_path, format='PNG', optimize=True)

        # Convert annotations
        # DocLayNet HF may use different field names across versions:
        #   v1.0: 'bboxes', 'categories'
        #   v1.1: 'bboxes_block', 'categories', or nested 'coco_bbox'
        # We try all known variants
        bboxes = (sample.get('bboxes') or sample.get('bboxes_block')
                  or sample.get('bbox') or sample.get('coco_bbox') or [])
        categories = (sample.get('categories') or sample.get('category')
                      or sample.get('category_id') or [])
        
        # Some versions store annotations as a dict with 'bbox' and 'category' keys
        if not bboxes and 'objects' in sample:
            obj = sample['objects']
            bboxes = obj.get('bbox', [])
            categories = obj.get('category', [])
            
        label_lines = []
        
        if isinstance(bboxes, list) and isinstance(categories, list):
            for bbox, cat_id in zip(bboxes, categories):
                if isinstance(cat_id, (list, tuple)):
                    cat_id = cat_id[0] if cat_id else -1
                    
                project_class = DOCLAYNET_TO_PROJECT.get(int(cat_id))
                if project_class is None:
                    continue

                # Convert COCO → YOLO
                x_c, y_c, w_n, h_n = coco_to_yolo(bbox, img_width, img_height)
                
                # Skip tiny annotations
                if w_n < 0.005 or h_n < 0.005:
                    continue

                label_lines.append(f"{project_class} {x_c:.6f} {y_c:.6f} {w_n:.6f} {h_n:.6f}")
                class_counts[PROJECT_CLASSES[project_class]] = class_counts.get(PROJECT_CLASSES[project_class], 0) + 1
                stats['annotations'] += 1

        # Write label file (even if empty — YOLO handles empty labels)
        label_path = os.path.join(lbl_dir, filename.replace('.png', '.txt'))
        with open(label_path, 'w') as f:
            f.write('\n'.join(label_lines))

        stats['total'] += 1
        if is_val:
            stats['val'] += 1
        else:
            stats['train'] += 1

    return stats, class_counts


def process_local_coco(local_path, output_dir, val_split):
    """Process local DocLayNet COCO format download."""
    from tqdm import tqdm

    # DocLayNet local structure: COCO/train.json, COCO/val.json, PNG/
    coco_dir = os.path.join(local_path, 'COCO')
    png_dir = os.path.join(local_path, 'PNG')
    
    if not os.path.isdir(coco_dir):
        # Try alternative structure
        coco_dir = local_path
        
    images_train = os.path.join(output_dir, 'images', 'train')
    images_val = os.path.join(output_dir, 'images', 'val')
    labels_train = os.path.join(output_dir, 'labels', 'train')
    labels_val = os.path.join(output_dir, 'labels', 'val')

    for d in [images_train, images_val, labels_train, labels_val]:
        os.makedirs(d, exist_ok=True)

    stats = {'total': 0, 'train': 0, 'val': 0, 'annotations': 0, 'skipped': 0}
    class_counts = {v: 0 for v in PROJECT_CLASSES.values()}

    # Process each split
    for split_file in ['train.json', 'val.json', 'test.json']:
        json_path = os.path.join(coco_dir, split_file)
        if not os.path.exists(json_path):
            continue

        print(f"\nProcessing {split_file}...")
        with open(json_path, 'r') as f:
            coco = json.load(f)

        # Build image_id → image_info mapping
        images_map = {img['id']: img for img in coco.get('images', [])}
        
        # Build image_id → annotations mapping
        anns_by_image = {}
        for ann in coco.get('annotations', []):
            img_id = ann['image_id']
            anns_by_image.setdefault(img_id, []).append(ann)

        for img_id, img_info in tqdm(images_map.items(), desc=f"  {split_file}"):
            file_name = img_info['file_name']
            img_width = img_info['width']
            img_height = img_info['height']

            # Find source image
            src_path = None
            for candidate in [
                os.path.join(png_dir, file_name),
                os.path.join(local_path, 'PNG', file_name),
                os.path.join(local_path, file_name),
            ]:
                if os.path.exists(candidate):
                    src_path = candidate
                    break

            if not src_path:
                stats['skipped'] += 1
                continue

            # Determine split (val.json → val, everything else → train)
            is_val = 'val' in split_file
            img_dir = images_val if is_val else images_train
            lbl_dir = labels_val if is_val else labels_train

            # Copy image
            dst_path = os.path.join(img_dir, file_name)
            shutil.copy2(src_path, dst_path)

            # Convert annotations
            anns = anns_by_image.get(img_id, [])
            label_lines = []

            for ann in anns:
                cat_id = ann.get('category_id', -1)
                project_class = DOCLAYNET_TO_PROJECT.get(cat_id)
                if project_class is None:
                    continue

                bbox = ann.get('bbox', [0, 0, 0, 0])
                x_c, y_c, w_n, h_n = coco_to_yolo(bbox, img_width, img_height)
                
                if w_n < 0.005 or h_n < 0.005:
                    continue

                label_lines.append(f"{project_class} {x_c:.6f} {y_c:.6f} {w_n:.6f} {h_n:.6f}")
                class_counts[PROJECT_CLASSES[project_class]] = class_counts.get(PROJECT_CLASSES[project_class], 0) + 1
                stats['annotations'] += 1

            stem = os.path.splitext(file_name)[0]
            label_path = os.path.join(lbl_dir, f"{stem}.txt")
            with open(label_path, 'w') as f:
                f.write('\n'.join(label_lines))

            stats['total'] += 1
            if is_val:
                stats['val'] += 1
            else:
                stats['train'] += 1

    return stats, class_counts


def write_data_yaml(output_dir):
    """Write the YOLO data.yaml configuration file."""
    yaml_content = f"""# Document Layout Detection - YOLO Dataset Config
# Generated by prepare_doclaynet.py
# Source: DocLayNet (IBM) — remapped to 8 project classes

path: {os.path.abspath(output_dir)}
train: images/train
val: images/val

nc: 8
names:
  0: text_block
  1: table
  2: figure
  3: signature
  4: stamp
  5: handwriting_region
  6: header
  7: footer

# Note: Classes 3 (signature), 4 (stamp), 5 (handwriting_region) are NOT
# present in DocLayNet. You must add annotated examples for these classes
# manually (see docs/DATA_ANNOTATION_PLAN.md).
# Use Roboflow or Label Studio to annotate your own documents.
"""
    yaml_path = os.path.join(output_dir, 'data.yaml')
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    print(f"  Wrote {yaml_path}")
    return yaml_path


def main():
    parser = argparse.ArgumentParser(description="Download and convert DocLayNet to YOLO format")
    parser.add_argument('--output', default='models/yolo/data', help='Output directory')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of images (0 = all ~80K)')
    parser.add_argument('--val-split', type=float, default=0.2, help='Validation split ratio (default: 0.2)')
    parser.add_argument('--local', type=str, default='', help='Path to local DocLayNet download (skip HF download)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    args = parser.parse_args()

    random.seed(args.seed)

    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("DocLayNet -> YOLO Conversion")
    print("=" * 60)
    print(f"  Output: {os.path.abspath(output_dir)}")
    print(f"  Val split: {args.val_split}")
    if args.limit:
        print(f"  Limit: {args.limit} images")
    print()

    # Class mapping summary
    print("Class mapping (DocLayNet -> Project):")
    for dl_id, proj_id in sorted(DOCLAYNET_TO_PROJECT.items()):
        dl_names = ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer',
                     'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title']
        print(f"  {dl_names[dl_id]:15s} -> {PROJECT_CLASSES[proj_id]}")
    print()

    if args.local:
        # Local COCO format
        print(f"Using local DocLayNet: {args.local}")
        stats, class_counts = process_local_coco(args.local, output_dir, args.val_split)
    else:
        # Download from Hugging Face
        ds, total = download_doclaynet(output_dir, args.limit)
        stats, class_counts = process_hf_dataset(ds, total, output_dir, args.val_split)

    # Write data.yaml
    write_data_yaml(output_dir)

    # Report
    print("\n" + "=" * 60)
    print("Conversion Complete!")
    print("=" * 60)
    print(f"  Total images: {stats['total']} (train: {stats['train']}, val: {stats['val']})")
    print(f"  Total annotations: {stats['annotations']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"\n  Class distribution:")
    for cls_name, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        pct = (count / max(stats['annotations'], 1)) * 100
        bar = "#" * int(pct / 2)
        print(f"    {cls_name:20s}: {count:6d} ({pct:5.1f}%) {bar}")

    missing = [n for n in ['signature', 'stamp', 'handwriting_region'] if class_counts.get(n, 0) == 0]
    if missing:
        print(f"\n  WARNING: Missing classes (not in DocLayNet): {', '.join(missing)}")
        print("    -> Add annotated examples manually or via Roboflow/Label Studio")
        print("    -> The model will still learn the 5 present classes and can be fine-tuned later")

    print(f"\n  Next steps:")
    print(f"    1. (Optional) Add signature/stamp/handwriting annotations")
    print(f"    2. Train: python scripts/train_document_yolo.py --data {os.path.join(output_dir, 'data.yaml')}")
    print(f"    3. Model output: models/yolo/document_layout.pt")


if __name__ == '__main__':
    main()

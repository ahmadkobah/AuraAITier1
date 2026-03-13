"""
Convert all cached DocLayNet parquet shards to YOLO format.
Reads directly from HuggingFace cache — no download needed.
"""
import glob
import io
import os
import random
import sys
from pathlib import Path

# Class remapping: DocLayNet 11 classes -> Project 8 classes
DOCLAYNET_TO_PROJECT = {
    0: 0,   # Caption -> text_block
    1: 0,   # Footnote -> text_block
    2: 0,   # Formula -> text_block
    3: 0,   # List-item -> text_block
    4: 7,   # Page-footer -> footer
    5: 6,   # Page-header -> header
    6: 2,   # Picture -> figure
    7: 6,   # Section-header -> header
    8: 1,   # Table -> table
    9: 0,   # Text -> text_block
    10: 6,  # Title -> header
}

PROJECT_CLASSES = {
    0: 'text_block', 1: 'table', 2: 'figure', 3: 'signature',
    4: 'stamp', 5: 'handwriting_region', 6: 'header', 7: 'footer',
}


def coco_to_yolo(bbox, img_w, img_h):
    x, y, w, h = bbox
    xc = (x + w / 2) / img_w
    yc = (y + h / 2) / img_h
    wn = w / img_w
    hn = h / img_h
    return (
        max(0.0, min(1.0, xc)),
        max(0.0, min(1.0, yc)),
        max(0.0, min(1.0, wn)),
        max(0.0, min(1.0, hn)),
    )


def find_cached_shards():
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub",
                             "datasets--ds4sd--DocLayNet-v1.1")
    if not os.path.isdir(cache_dir):
        print(f"ERROR: HF cache not found at {cache_dir}")
        sys.exit(1)

    shards = sorted(glob.glob(os.path.join(cache_dir, "**", "*.parquet"), recursive=True))
    # Only train shards
    shards = [s for s in shards if "train" in os.path.basename(s)]
    return shards


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="models/yolo/data")
    parser.add_argument("--val-split", type=float, default=0.15)
    parser.add_argument("--limit", type=int, default=0, help="Max images total (0=all)")
    args = parser.parse_args()

    shards = find_cached_shards()
    print(f"Found {len(shards)} cached parquet shards")
    if not shards:
        sys.exit(1)

    import pyarrow.parquet as pq
    from PIL import Image as PILImage

    out = args.output
    dirs = {
        "img_train": os.path.join(out, "images", "train"),
        "img_val": os.path.join(out, "images", "val"),
        "lbl_train": os.path.join(out, "labels", "train"),
        "lbl_val": os.path.join(out, "labels", "val"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    stats = {"total": 0, "train": 0, "val": 0, "annotations": 0, "skipped": 0}
    class_counts = {name: 0 for name in PROJECT_CLASSES.values()}

    # Collect all row indices across shards, then split
    # Process shard by shard to limit memory
    global_idx = 0
    all_indices = []

    # First pass: count rows per shard
    shard_rows = []
    for shard in shards:
        meta = pq.read_metadata(shard)
        shard_rows.append(meta.num_rows)
        print(f"  {os.path.basename(shard)}: {meta.num_rows} rows")

    total_rows = sum(shard_rows)
    limit = args.limit if args.limit > 0 else total_rows
    limit = min(limit, total_rows)
    print(f"\nTotal available: {total_rows}, will process: {limit}")

    # Build global index list and shuffle for split
    random.seed(42)
    all_global = list(range(limit))
    random.shuffle(all_global)
    val_count = int(limit * args.val_split)
    val_set = set(all_global[:val_count])

    print(f"Split: {limit - val_count} train, {val_count} val")
    print(f"\nConverting...")

    processed = 0
    for shard_i, shard_path in enumerate(shards):
        if processed >= limit:
            break

        print(f"\n[Shard {shard_i+1}/{len(shards)}] {os.path.basename(shard_path)}")
        table = pq.read_table(shard_path)
        n_rows = len(table)

        for row_i in range(n_rows):
            if processed >= limit:
                break

            try:
                row = {col: table.column(col)[row_i].as_py() for col in table.column_names}
            except Exception:
                stats["skipped"] += 1
                processed += 1
                continue

            # Extract image
            img_data = row.get("image", {})
            try:
                if isinstance(img_data, dict) and "bytes" in img_data:
                    img = PILImage.open(io.BytesIO(img_data["bytes"]))
                elif isinstance(img_data, bytes):
                    img = PILImage.open(io.BytesIO(img_data))
                else:
                    stats["skipped"] += 1
                    processed += 1
                    continue
            except Exception:
                stats["skipped"] += 1
                processed += 1
                continue

            img_w, img_h = img.size
            if img_w < 10 or img_h < 10:
                stats["skipped"] += 1
                processed += 1
                continue

            # Resize if needed
            max_dim = max(img_w, img_h)
            if max_dim > 1024:
                scale = 1024 / max_dim
                img_w, img_h = int(img_w * scale), int(img_h * scale)
                img = img.resize((img_w, img_h))

            # Split
            is_val = processed in val_set
            img_dir = dirs["img_val"] if is_val else dirs["img_train"]
            lbl_dir = dirs["lbl_val"] if is_val else dirs["lbl_train"]

            fname = f"doclaynet_{processed:06d}.png"
            img.save(os.path.join(img_dir, fname), format="PNG", optimize=True)

            # Annotations
            bboxes = row.get("bboxes") or row.get("bboxes_block") or row.get("bbox") or []
            categories = row.get("categories") or row.get("category") or row.get("category_id") or []
            if not bboxes and "objects" in row:
                obj = row["objects"]
                bboxes = obj.get("bbox", [])
                categories = obj.get("category", [])

            lines = []
            if isinstance(bboxes, list) and isinstance(categories, list):
                for bbox, cat in zip(bboxes, categories):
                    if isinstance(cat, (list, tuple)):
                        cat = cat[0] if cat else -1
                    pc = DOCLAYNET_TO_PROJECT.get(int(cat))
                    if pc is None:
                        continue
                    xc, yc, wn, hn = coco_to_yolo(bbox, img_w, img_h)
                    if wn < 0.005 or hn < 0.005:
                        continue
                    lines.append(f"{pc} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}")
                    class_counts[PROJECT_CLASSES[pc]] += 1
                    stats["annotations"] += 1

            lbl_path = os.path.join(lbl_dir, fname.replace(".png", ".txt"))
            with open(lbl_path, "w") as f:
                f.write("\n".join(lines))

            stats["total"] += 1
            if is_val:
                stats["val"] += 1
            else:
                stats["train"] += 1

            processed += 1

            if processed % 2000 == 0:
                print(f"  ... {processed}/{limit} images processed")

        # Free memory
        del table

    print(f"\n{'='*50}")
    print(f"Conversion complete!")
    print(f"  Total:       {stats['total']}")
    print(f"  Train:       {stats['train']}")
    print(f"  Val:         {stats['val']}")
    print(f"  Annotations: {stats['annotations']}")
    print(f"  Skipped:     {stats['skipped']}")
    print(f"\nClass distribution:")
    for name, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count}")
    print(f"\nOutput: {os.path.abspath(out)}")


if __name__ == "__main__":
    main()

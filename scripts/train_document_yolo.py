"""
Train YOLOv8 on document layout detection classes.

Usage:
    python scripts/train_document_yolo.py [--base yolov8n.pt] [--epochs 100] [--imgsz 1024]

Prerequisites:
    1. Annotated data in models/yolo/data/ (see docs/DATA_ANNOTATION_PLAN.md)
    2. ultralytics package installed (already in requirements.txt)

Output:
    models/yolo/document_layout.pt
"""

import argparse
import os
import sys
import shutil

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def validate_dataset(data_yaml: str) -> bool:
    """Check that dataset structure exists and has minimum images."""
    import yaml

    if not os.path.exists(data_yaml):
        print(f"ERROR: {data_yaml} not found. See docs/DATA_ANNOTATION_PLAN.md")
        return False

    with open(data_yaml, 'r') as f:
        cfg = yaml.safe_load(f)

    base = cfg.get('path', os.path.dirname(data_yaml))
    if not os.path.isabs(base):
        base = os.path.join(os.path.dirname(os.path.abspath(data_yaml)), base)
    train_dir = os.path.join(base, cfg.get('train', 'images/train'))
    val_dir = os.path.join(base, cfg.get('val', 'images/val'))

    for d, name in [(train_dir, 'train'), (val_dir, 'val')]:
        if not os.path.isdir(d):
            print(f"ERROR: {name} images directory not found: {d}")
            return False
        count = len([f for f in os.listdir(d) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        print(f"  {name}: {count} images")
        if count < 10:
            print(f"  WARNING: Very few {name} images ({count}). Need at least 100+ for useful training.")

    nc = cfg.get('nc', 0)
    names = cfg.get('names', {})
    print(f"  Classes: {nc} — {list(names.values())}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Train document layout YOLO model")
    parser.add_argument('--base', default='yolov8n.pt', help='Base YOLO model (yolov8n.pt or yolov8s.pt)')
    parser.add_argument('--epochs', type=int, default=100, help='Training epochs')
    parser.add_argument('--imgsz', type=int, default=1024, help='Image size')
    parser.add_argument('--batch', type=int, default=8, help='Batch size')
    parser.add_argument('--data', default='models/yolo/data/data.yaml', help='Dataset YAML path')
    parser.add_argument('--device', default='0', help='CUDA device (0, 1, or cpu)')
    parser.add_argument('--output', default='models/yolo/document_layout.pt', help='Output model path')
    args = parser.parse_args()

    print("=" * 60)
    print("Document Layout YOLO Training")
    print("=" * 60)

    # Validate dataset
    print("\nValidating dataset...")
    if not validate_dataset(args.data):
        sys.exit(1)

    # Import and train
    from ultralytics import YOLO

    print(f"\nLoading base model: {args.base}")
    model = YOLO(args.base)

    print(f"Starting training: {args.epochs} epochs, imgsz={args.imgsz}, batch={args.batch}")
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project='models/yolo/runs',
        name='document_layout',
        exist_ok=True,
        # Augmentation settings tuned for documents
        hsv_h=0.0,     # No hue shift (documents aren't color-dependent)
        hsv_s=0.1,     # Minimal saturation change
        hsv_v=0.2,     # Small brightness variation (scan quality)
        degrees=3.0,   # Slight rotation (skewed scans)
        translate=0.05,
        scale=0.2,
        flipud=0.0,    # Never flip vertically (text orientation matters)
        fliplr=0.0,    # Never flip horizontally (text direction matters)
        mosaic=0.5,    # Reduced mosaic (document layout is full-page)
    )

    # Copy best model to output path
    best_path = os.path.join('models', 'yolo', 'runs', 'document_layout', 'weights', 'best.pt')
    if os.path.exists(best_path):
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        shutil.copy2(best_path, args.output)
        print(f"\n✓ Best model saved to: {args.output}")
        print(f"  Model size: {os.path.getsize(args.output) / 1024 / 1024:.1f} MB")
    else:
        print(f"\nWARNING: Best model not found at {best_path}")

    # Validate
    print("\nRunning validation...")
    metrics = model.val()
    print(f"  mAP@50: {metrics.box.map50:.3f}")
    print(f"  mAP@50-95: {metrics.box.map:.3f}")

    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()

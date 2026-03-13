# Document Layout Model — Data Collection & Annotation Plan

## Goal
Train a YOLOv8n/s model on document-specific classes to replace the generic COCO model
for accurate detection of signatures, handwriting, tables, stamps, and text regions.

## Target Classes (8)

| Class ID | Class Name | Description |
|---|---|---|
| 0 | `text_block` | Printed body text paragraphs |
| 1 | `table` | Any tabular structure (with or without borders) |
| 2 | `figure` | Charts, images, logos, diagrams |
| 3 | `signature` | Handwritten signatures (ink strokes) |
| 4 | `stamp` | Company stamps, seals, watermarks |
| 5 | `handwriting_region` | Handwritten notes, annotations, filled-in fields |
| 6 | `header` | Page headers, letterheads |
| 7 | `footer` | Page footers, page numbers |

## Data Requirements

| Item | Target |
|---|---|
| Total annotated pages | 2,000–5,000 |
| Mix: invoices | ~40% |
| Mix: contracts/letters | ~25% |
| Mix: forms (filled-in) | ~20% |
| Mix: mixed/other | ~15% |
| Annotation format | YOLO (`.txt` per image, class x_center y_center width height) |
| Image resolution | 1024px longest side (uniform) |

## Data Sources

1. **Existing uploads** — `data/uploads/` and processed documents from production
2. **DocLayNet** (IBM) — 80,863 pages with 11 classes (remap to our 8)
3. **PubLayNet** (IBM) — 360,000 pages with 5 classes (supplement tables & figures)
4. **Manual annotation** — Signatures, stamps, handwriting from real documents

## Annotation Tool

**Recommended:** [Label Studio](https://labelstud.io/) (self-hosted) or [Roboflow](https://roboflow.com/) (cloud)

- Export format: YOLOv8 (one `.txt` file per image)
- Each line: `class_id x_center y_center width height` (normalized 0-1)

## Directory Structure

```
models/yolo/
├── document_layout.pt          # Final trained model
├── data/
│   ├── images/
│   │   ├── train/              # 80% of annotated images
│   │   └── val/                # 20% of annotated images
│   ├── labels/
│   │   ├── train/              # Corresponding YOLO .txt annotations
│   │   └── val/
│   └── data.yaml               # Dataset config for Ultralytics
```

## data.yaml Template

```yaml
path: models/yolo/data
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
```

## DocLayNet Class Remapping

| DocLayNet Class | → Our Class |
|---|---|
| Text | text_block |
| Title | header |
| Section-header | header |
| Table | table |
| Figure/Picture | figure |
| Caption | text_block |
| Footnote | footer |
| Page-header | header |
| Page-footer | footer |
| List-item | text_block |
| Formula | text_block |

**Note:** DocLayNet has no signature/stamp/handwriting classes — these must come from
manual annotation of production documents or a custom dataset.

## Quality Checklist

- [ ] At least 100 examples per class (minimum for YOLO to learn)
- [ ] At least 500 examples for `signature` and `handwriting_region` (rare classes)
- [ ] Bounding boxes tight around content (no excessive padding)
- [ ] Mixed document orientations (portrait + landscape)
- [ ] Mixed scan qualities (clean + noisy + skewed)
- [ ] Train/val split is stratified (each class proportionally represented)

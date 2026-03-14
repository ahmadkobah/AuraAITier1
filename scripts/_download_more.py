"""
Download additional datasets for signature, stamp, and handwriting from Roboflow Universe.
Then balance all classes in the final dataset.
"""
import os
import sys
import shutil
from pathlib import Path

API_KEY = "D6CSnT6JnSXemNcmySCZ"
DOWNLOADS = Path(__file__).parent.parent / "models" / "yolo" / "downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

def try_download(workspace, project, version, name):
    """Try to download a Roboflow dataset. Returns path on success, None on failure."""
    from roboflow import Roboflow
    target = DOWNLOADS / name
    try:
        rf = Roboflow(api_key=API_KEY)
        proj = rf.workspace(workspace).project(project)
        ver = proj.version(version)
        ver.download("yolov8", location=str(target))
        # Count files
        count = sum(1 for _ in target.rglob("*.jpg")) + sum(1 for _ in target.rglob("*.png"))
        print(f"  OK: {workspace}/{project} v{version} -> {count} images")
        return target
    except Exception as e:
        err = str(e)[:120]
        print(f"  FAIL: {workspace}/{project} v{version} -> {err}")
        return None

def main():
    # ========================
    # SIGNATURE - need ~5000+ more
    # ========================
    print("=" * 60)
    print("DOWNLOADING MORE SIGNATURE DATASETS")
    print("=" * 60)
    
    sig_candidates = [
        # Large signature datasets on Roboflow Universe
        ("minaehyeon", "signature-oclmx", 2, "sig_minaehyeon"),
        ("signdetect-y7mxl", "signdetect", 1, "sig_signdetect"),
        ("signature-detection-u9drl", "signature-detection", 1, "sig_detect1"),
        ("signature-detection-cghft", "signature-detection", 1, "sig_detect2"),
        ("a-bfhmz", "signature-detection-y0cke", 1, "sig_abfhmz"),
        ("signature-detection-xc8up", "signature-detection-o9arg", 1, "sig_xc8up"),
        ("object-detection-xgbkp", "signature", 1, "sig_objdet"),
        ("objectdetectionfordocuments", "signaturedetection", 1, "sig_docdet"),
        ("practice-bnwlb", "signature-detection-ffxtn", 1, "sig_practice"),
        ("signaturedetection-rtugo", "signaturedetection", 1, "sig_rtugo"),
        ("work-jhwgx", "signature-detection-txxue", 1, "sig_work"),
        ("project-nnb1p", "signatures-detection", 1, "sig_proj"),
        ("project-bftzv", "signature_detection", 1, "sig_projb"),
        ("dl-final", "signatue-detection", 1, "sig_dlfinal"),
    ]
    
    for ws, proj, ver, name in sig_candidates:
        if (DOWNLOADS / name).exists():
            count = sum(1 for _ in (DOWNLOADS / name).rglob("*.jpg")) + sum(1 for _ in (DOWNLOADS / name).rglob("*.png"))
            print(f"  SKIP (exists): {name} - {count} images")
            continue
        try_download(ws, proj, ver, name)
    
    # ========================
    # STAMP - need ~5000+ more
    # ========================
    print("\n" + "=" * 60)
    print("DOWNLOADING MORE STAMP DATASETS")
    print("=" * 60)
    
    stamp_candidates = [
        ("stamp-detection-pchbm", "stamp-detection", 1, "stp_moein"),
        ("russian-documents", "stamp-detection-mhsxk", 1, "stp_russian"),
        ("seal-detection-kpbrj", "seal-detection", 1, "stp_seal1"),
        ("stamp-fxflb", "stamp-detection-ejeee", 1, "stp_fxflb"),
        ("stamp-dcmiz", "stamp-detect", 1, "stp_dcmiz"),
        ("stempel", "stamp-ehkgc", 1, "stp_stempel"),
        ("seal-detection-zfhcf", "seal-detection", 1, "stp_seal2"),
        ("stamps-hbkyo", "stamp-detection", 1, "stp_hbkyo"),
        ("stamp-detection-yuhyf", "stamp-detection", 1, "stp_yuhyf"),
        ("project-ug5nt", "stamps", 1, "stp_projug5"),
    ]
    
    for ws, proj, ver, name in stamp_candidates:
        if (DOWNLOADS / name).exists():
            count = sum(1 for _ in (DOWNLOADS / name).rglob("*.jpg")) + sum(1 for _ in (DOWNLOADS / name).rglob("*.png"))
            print(f"  SKIP (exists): {name} - {count} images")
            continue
        try_download(ws, proj, ver, name)
    
    # ========================
    # HANDWRITING - need ~5000+ more
    # ========================
    print("\n" + "=" * 60)
    print("DOWNLOADING MORE HANDWRITING DATASETS")
    print("=" * 60)
    
    hw_candidates = [
        ("handwriting-recognition-pkr2t", "handwriting-recognition", 1, "hw_recog1"),
        ("handwritten-text-lqbbb", "handwritten-text", 1, "hw_text1"),
        ("handwriting-detection-f8vya", "handwriting-detection", 1, "hw_detect1"),
        ("handwriting-jjxze", "handwriting-detection", 1, "hw_jjxze"),
        ("handwriting-detection-bvjvv", "handwriting-detection", 1, "hw_bvjvv"),
        ("handwritten-detection", "handwritten-detection", 1, "hw_det2"),
        ("handwritten-u1f8n", "handwritten-text-detection", 1, "hw_u1f8n"),
        ("handwriting-segmentation", "handwriting", 1, "hw_seg"),
        ("the-university-of-memphis", "handwritten-text-recognition", 2, "hw_memphis"),
        ("hw-region-detect", "handwriting-region", 1, "hw_region"),
    ]
    
    for ws, proj, ver, name in hw_candidates:
        if (DOWNLOADS / name).exists():
            count = sum(1 for _ in (DOWNLOADS / name).rglob("*.jpg")) + sum(1 for _ in (DOWNLOADS / name).rglob("*.png"))
            print(f"  SKIP (exists): {name} - {count} images")
            continue
        try_download(ws, proj, ver, name)
    
    # Summary
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    for d in sorted(DOWNLOADS.iterdir()):
        if d.is_dir():
            imgs = sum(1 for _ in d.rglob("*.jpg")) + sum(1 for _ in d.rglob("*.png"))
            lbls = sum(1 for _ in d.rglob("*.txt")) 
            print(f"  {d.name}: {imgs} images, {lbls} label files")


if __name__ == "__main__":
    main()

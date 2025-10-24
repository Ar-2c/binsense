# ml/model.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
from ultralytics import YOLO

# sökväg till modellvikter och modellversion
WEIGHTS_PATH = Path(__file__).parent / "best.pt"
MODEL_VERSION = "yolo_poc_v1"

# funktion för att ladda modell
def load_model(weights: Optional[str | Path] = None) -> YOLO:
    w = Path(weights) if weights else WEIGHTS_PATH
    if not w.exists():
        raise FileNotFoundError(f"Viktfil saknas: {w.resolve()}")
    return YOLO(str(w))

# preditkioner av bins
def predict_bins(ultra_model, image_path, conf: float = 0.25):
    p = str(Path(image_path))
    results = ultra_model.predict(p)

    names = getattr(ultra_model, "names", {}) or {}
    out = []
    for r in results:
        if r.boxes is None:
            continue
        for b in r.boxes:
            xyxy = b.xyxy[0].tolist()
            c = float(b.conf[0].item())
            if c < conf:
                continue
            idx = int(b.cls[0].item())
            out.append({
                "class_idx": idx,
                "class_name": names.get(idx, "unknown"),
                "confidence": c,
                "bbox": xyxy,
                "raw": {"xyxy": xyxy, "conf": c, "cls_idx": idx},
            })
    return out





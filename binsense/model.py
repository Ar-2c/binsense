# binsense/model.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
from ultralytics import YOLO

# === Konfig (ändra vid behov) ===
WEIGHTS_PATH = Path("models/best.pt")   # peka på er viktfil
MODEL_VERSION = "yolo_poc_v1"           # byt när ni versionerar

# === Modell-laddning ===
# Vi cache:ar inte med Streamlit här, utan låter anroparen (Streamlit-sidan) cache:a.
def load_model(weights: Optional[str | Path] = None) -> YOLO:
    w = Path(weights) if weights else WEIGHTS_PATH
    if not w.exists():
        raise FileNotFoundError(f"Viktfil saknas: {w.resolve()}")
    return YOLO(str(w))

# === Prediktion ===
# binsense/model.py
from pathlib import Path

def predict_bins(ultra_model, image_path, conf: float = 0.25):
    p = str(Path(image_path))
    results = ultra_model.predict(p)  # v8-säkert, inga kwargs

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





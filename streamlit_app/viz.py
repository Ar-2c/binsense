# binsense/viz.py
from __future__ import annotations
import json
from typing import Iterable, Mapping
from PIL import Image, ImageDraw, ImageFont

def _measure_text(draw, label: str, font):
    try:
        if hasattr(draw, "textbbox"):
            l, t, r, b = draw.textbbox((0, 0), label, font=font)
            return r - l, b - t
    except Exception:
        pass
    try:
        if font is not None and hasattr(font, "getbbox"):
            l, t, r, b = font.getbbox(label)
            return r - l, b - t
    except Exception:
        pass
    try:
        if hasattr(draw, "textsize"):
            return draw.textsize(label, font=font)
    except Exception:
        pass
    return 0, 0

def draw_boxes(img: Image.Image, preds: Iterable[Mapping]) -> Image.Image:
    """preds innehåller fält: class, confidence, bbox_xyxy (json/obj)."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for p in preds:
        bbox_field = p.get("bbox_xyxy")
        if isinstance(bbox_field, str):
            try:
                bb = json.loads(bbox_field)
            except Exception:
                continue
        else:
            bb = bbox_field or {}

        try:
            x1 = float(bb.get("x1", 0)); y1 = float(bb.get("y1", 0))
            x2 = float(bb.get("x2", 0)); y2 = float(bb.get("y2", 0))
        except Exception:
            continue

        label = f"{p.get('class','?')} {float(p.get('confidence',0))*100:.0f}%"
        draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=3)

        tw, th = _measure_text(draw, label, font)
        pad = 3
        bg = [x1, max(0, y1 - th - 2*pad), x1 + tw + 2*pad, y1]
        draw.rectangle(bg, fill=(255, 0, 0))
        if font:
            draw.text((x1 + pad, max(0, y1 - th - pad)), label, fill=(255, 255, 255), font=font)
    return out

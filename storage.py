# binsense/storage.py
from __future__ import annotations
import io
from typing import Optional
from PIL import Image

_HAS_REQUESTS = None  # lazy

def _ensure_requests():
    global _HAS_REQUESTS
    if _HAS_REQUESTS is None:
        try:
            import requests  # noqa
            _HAS_REQUESTS = True
        except Exception:
            _HAS_REQUESTS = False
    return _HAS_REQUESTS

def load_image_from_uri(uri: str) -> Optional[Image.Image]:
    """Öppna lokalt eller http(s) → PIL.Image (RGB) eller None."""
    try:
        if uri.lower().startswith("http"):
            if not _ensure_requests():
                return None
            import requests
            r = requests.get(uri, timeout=10)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        else:
            return Image.open(uri).convert("RGB")
    except Exception:
        return None

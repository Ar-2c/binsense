from pathlib import Path
from ultralytics import YOLO, __version__

print("Ultralytics version:", __version__)

weights = Path("models/best.pt")  # ändra om dina vikter ligger annanstans
img     = Path("data/uploads").rglob("*.png")
img     = next(img, None) or Path("data/uploads").rglob("*.jpg").__iter__().__next__()

print("Weights:", weights.resolve())
print("Image:  ", img.resolve())

m = YOLO(str(weights))
res = m.predict(str(img))  # <-- v8-sättet, utan conf-kwargs
print("OK. Results objects:", type(res), "len:", len(res))
print("First result has boxes:", res[0].boxes is not None)

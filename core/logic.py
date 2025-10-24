# core/logic.py
from __future__ import annotations
import pandas as pd

NEED_CLASSES = {"full", "overfull", "bin_full", "bin_overfull"}

def room_needs_empty(preds: pd.DataFrame, threshold: float) -> tuple[bool, int, int, float]:
    """
    Returnerar (need_flag, need_count, total_bins, ratio_full).
    - threshold = andel fulla kärl som krävs, t.ex. 0.90.
    """
    if preds is None or preds.empty or "class" not in preds.columns:
        return False, 0, 0, 0.0
    classes = preds["class"].astype(str).str.lower()
    total = len(classes)
    need_count = int(classes.isin(NEED_CLASSES).sum())
    ratio = (need_count / total) if total else 0.0
    return ((ratio >= threshold) if total else False, need_count, total, ratio)
# binsense_app/pages/2_Site_detalj.py

import io
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import text

try:
    import requests  # valfritt: för att hämta bilder från http(s) om image_uri är en URL
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

# --- skydd / logout ---
def require_login():
    if not st.session_state.get("user"):
        st.switch_page("app.py")

def sidebar_userbox():
    u = st.session_state.get("user", {})
    with st.sidebar:
        st.caption(f"👤 {u.get('name','okänd')} • tenant {u.get('tenant_id','-')}")
        if st.button("Logga ut"):
            st.session_state.pop("user", None)
            st.experimental_rerun()

require_login()
sidebar_userbox()

st.set_page_config(page_title="Binsense – Site detalj", layout="wide")
st.title("Site – detalj")

# -----------------------------
# DB
# -----------------------------
from binsense.db import get_engine
eng = get_engine()
st.caption(f"[Detalj] DB: {eng.url}")

# -----------------------------
# Hjälpare
# -----------------------------
def load_image_from_uri(uri: str) -> Image.Image | None:
    """
    Försök öppna bild både lokalt och via http(s).
    Returnerar PIL.Image eller None om det misslyckas.
    """
    try:
        if uri.lower().startswith("http"):
            if not HAS_REQUESTS:
                # Streamlit kan visa URL direkt, men för ritning behöver vi bytes → kräver requests.
                return None
            r = requests.get(uri, timeout=10)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        else:
            return Image.open(uri).convert("RGB")
    except Exception:
        return None

def _measure_text(draw: ImageDraw.ImageDraw, label: str, font):
    """
    Robust textmått som funkar i både nya/äldre Pillow:
    - draw.textbbox (nyare)
    - font.getbbox (nyare)
    - draw.textsize (äldre)
    """
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

    # Fallback för äldre Pillow
    try:
        if hasattr(draw, "textsize"):
            return draw.textsize(label, font=font)
    except Exception:
        pass

    return 0, 0


def draw_boxes(img: Image.Image, preds: list[dict]) -> Image.Image:
    """
    Rita bounding boxes på en kopia av bilden.
    Varje pred: {"class":..., "confidence":..., "bbox_xyxy": jsonb}
    """
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
            x1 = float(bb.get("x1", 0))
            y1 = float(bb.get("y1", 0))
            x2 = float(bb.get("x2", 0))
            y2 = float(bb.get("y2", 0))
        except Exception:
            continue

        label = f"{p.get('class','?')} {float(p.get('confidence',0))*100:.0f}%"

        # ruta
        draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=3)

        # label bakgrund
        tw, th = _measure_text(draw, label, font)
        pad = 3
        bg = [x1, max(0, y1 - th - 2*pad), x1 + tw + 2*pad, y1]
        draw.rectangle(bg, fill=(255, 0, 0))

        # label text
        if font:
            draw.text((x1 + pad, max(0, y1 - th - pad)), label, fill=(255, 255, 255), font=font)

    return out


# --- Nytt: definition av "fulla" klasser + funktion för tröskel-logik ---
NEED_CLASSES = {"full", "overfull", "bin_full", "bin_overfull"}

def room_needs_empty(preds_df: pd.DataFrame, threshold: float = 0.90):
    """
    Returnerar (need_flag, need_count, total_bins, ratio)
    - need_flag: True om andelen 'fulla' kärl >= threshold
    - need_count: antal 'fulla' kärl
    - total_bins: antal detekterade kärl
    - ratio: need_count / total_bins (0..1)
    Robust mot tom DF och saknad kolumn.
    """
    if preds_df is None or preds_df.empty or "class" not in preds_df.columns:
        return False, 0, 0, 0.0

    classes = preds_df["class"].astype(str).str.lower()
    total_bins = len(classes)
    need_count = int(classes.isin(NEED_CLASSES).sum())
    ratio = (need_count / total_bins) if total_bins else 0.0

    need_flag = (ratio >= threshold) if total_bins else False
    return need_flag, need_count, total_bins, ratio


# -----------------------------
# Välj site
# -----------------------------
# Hämta alla site_id som har data så dropdownen blir hjälpsam
with eng.begin() as conn:
    sites_df = pd.read_sql(text("""
        SELECT DISTINCT site_id FROM captures ORDER BY site_id
    """), conn)

site_options = sites_df["site_id"].astype(str).tolist()
# Tillåt deeplink från dashboard (st.query_params)
qp_site = st.query_params.get("site_id")
default_site = qp_site if qp_site in site_options else (site_options[0] if site_options else "")

site_id = st.selectbox("Välj site", options=site_options, index=(site_options.index(default_site) if default_site in site_options else 0) if site_options else 0)

if not site_id:
    st.info("Inga sites hittades.")
    st.stop()

# -----------------------------
# Välj capture för siten (lista senaste 50)
# -----------------------------
with eng.begin() as conn:
    caps = pd.read_sql(text("""
        SELECT id AS capture_id, image_uri, captured_at
        FROM captures
        WHERE site_id = :sid
        ORDER BY captured_at DESC
        LIMIT 50
    """), conn, params={"sid": site_id})

if caps.empty:
    st.info("Inga bilder hittades för den här siten ännu.")
    st.stop()

def _cap_label(row):
    ts = pd.to_datetime(row["captured_at"]).tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"{ts}  •  id={row['capture_id']}"

cap_labels = caps.apply(_cap_label, axis=1).tolist()
sel = st.selectbox("Välj bild (capture)", options=range(len(caps)), format_func=lambda i: cap_labels[i], index=0)

selected = caps.iloc[sel]
capture_id = selected["capture_id"]
image_uri = selected["image_uri"]
captured_at = selected["captured_at"]

# Läs prediktioner för vald capture
with eng.begin() as conn:
    preds = pd.read_sql(text("""
        SELECT class, confidence, bbox_xyxy, raw
        FROM bin_status
        WHERE capture_id = :cid
        ORDER BY confidence DESC
    """), conn, params={"cid": str(capture_id)})

# -----------------------------
# Visa bild + boxes
# -----------------------------
col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader(f"Senaste bild – site {site_id}")
    st.caption(f"captured_at: {captured_at} • capture_id: {capture_id}")

    img = load_image_from_uri(image_uri)
    if img is None:
        # Kan inte läsa bildbytes (t.ex. URL utan requests) → visa via st.image direkt
        st.image(image_uri, caption="(visad direkt från image_uri)", use_container_width=True)
    else:
        # Rita boxes
        pred_dicts = preds.to_dict("records")
        boxed = draw_boxes(img, pred_dicts)
        st.image(boxed, caption="Senaste bild med markerade kärl", use_container_width=True)

with col2:
    st.subheader("Detektioner (senaste)")
    if preds.empty:
        st.info("Inga detektioner i senaste bilden.")
    else:
        show = preds.rename(columns={
            "class": "Klass",
            "confidence": "Confidence",
        })[["Klass", "Confidence"]]
        # enklare procentsiffra
        show["Confidence"] = (show["Confidence"].astype(float) * 100).round(0).astype(int).astype(str) + " %"
        st.dataframe(show, use_container_width=True, hide_index=True)

        # --- Tröskel (slider) + robust summering ---
        thr = st.slider(
            "Tröskel: andel fulla kärl som krävs för 'TÖM'",
            min_value=0.0, max_value=1.0, value=0.90, step=0.05,
            help="Ex. 0.90 = minst 90 % av kärlen måste vara fulla (klass i {full, overfull, bin_full, bin_overfull})."
        )
        need_flag, need_count, total_bins, ratio = room_needs_empty(preds, threshold=thr)

        st.metric(
            "Behöver tömmas?",
            "Ja" if need_flag else "Nej",
            delta=f"{need_count}/{total_bins} kärl ({ratio:.0%}), tröskel {thr:.0%}"
        )

# -----------------------------
# Historik per bild (senaste 50)
# -----------------------------
st.subheader("Historik (senaste 50 bilder) – antal fulla / totalt")

# vilka klasser räknas som 'behöver tömmas'
NEED_CLAUSES_SQL = "('full','overfull','bin_full','bin_overfull')"

with eng.begin() as conn:
    hist_cap = pd.read_sql(
        text(f"""
            SELECT
              b.capture_id,
              c.captured_at,
              SUM((b.class IN {NEED_CLAUSES_SQL})::int) AS behov,
              COUNT(*) AS total
            FROM bin_status b
            JOIN captures c ON c.id = b.capture_id
            WHERE b.site_id = :sid
            GROUP BY b.capture_id, c.captured_at
            ORDER BY c.captured_at DESC
            LIMIT 50
        """),
        conn,
        params={"sid": site_id},
    )

if hist_cap.empty:
    st.info("Ingen historik ännu.")
else:
    # Gör en snygg tidsstämpel i UTC
    hist_cap["Tid (UTC)"] = (
        pd.to_datetime(hist_cap["captured_at"])
        .dt.tz_convert("UTC")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    # Skydda mot division med 0
    hist_cap["andel"] = hist_cap.apply(
        lambda r: (r["behov"] / r["total"]) if r["total"] else 0.0, axis=1
    )

    hist_cap["X/Y"] = (
        hist_cap["behov"].astype(int).astype(str)
        + "/"
        + hist_cap["total"].astype(int).astype(str)
    )
    hist_cap["Andel %"] = (hist_cap["andel"] * 100).round(0).astype(int).astype(str) + " %"

    show_cap = hist_cap[["Tid (UTC)", "capture_id", "X/Y", "Andel %"]]
    st.dataframe(show_cap, use_container_width=True, hide_index=True)
    st.caption("X = antal kärl som är fulla/överfulla i bilden, Y = totala detekterade kärl i bilden.")




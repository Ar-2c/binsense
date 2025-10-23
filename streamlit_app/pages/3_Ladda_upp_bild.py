# pages/3_Ladda_upp_bild.py

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()                     # <-- FLYTTAD HIT, allra först

import os
import json
import pathlib
from datetime import datetime, timezone
import tempfile

import streamlit as st
from sqlalchemy import text
from PIL import Image

from core.db import get_engine
from ml import model as bs_model
from core import storage        # <-- nu funkar env redan

# -----------------------------
# Sidinställningar + basic auth
# -----------------------------
st.set_page_config(page_title="Binsense – Ladda upp bild", layout="centered")

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

st.title("Ladda upp bild")

# -----------------------------
# Konfig / resurser
# -----------------------------
load_dotenv()
conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
engine = get_engine()
st.caption(f"[Upload] DB: {engine.url}")  # kan kommenteras bort när allt sitter

@st.cache_resource
def get_yolo():
    """Ladda YOLO en gång (cache)."""
    return bs_model.load_model()

yolo = get_yolo()

# -----------------------------
# DB helpers
# -----------------------------
def insert_capture(site_id: str, image_uri: str) -> tuple[str, datetime]:
    """INSERT i captures och returnera (capture_id, captured_at_utc)."""
    captured_at_utc = datetime.now(timezone.utc)
    q = text("""
        INSERT INTO captures (site_id, image_uri, captured_at, source)
        VALUES (:site_id, :image_uri, :captured_at, 'mobile')
        RETURNING id
    """)
    with engine.begin() as conn:
        row = conn.execute(q, {
            "site_id": site_id,
            "image_uri": image_uri,
            "captured_at": captured_at_utc,
        }).mappings().first()
    return row["id"], captured_at_utc

def insert_predictions(rows: list[dict]):
    """Bulk-INSERT i bin_status om rows finns."""
    if not rows:
        return
    q = text("""
        INSERT INTO bin_status
          (ts_utc, site_id, bin_id, class, confidence, bbox_xyxy, raw, capture_id, model_version)
        VALUES
          (:ts_utc, :site_id, :bin_id, :klass, :confidence,
           CAST(:bbox AS JSONB), CAST(:raw AS JSONB), :capture_id, :model_version)
    """)
    with engine.begin() as conn:
        conn.execute(q, rows)

# -----------------------------
# UI
# -----------------------------
site_id = st.text_input("Ange Site ID", placeholder="t.ex. 12A")
uploaded_file = st.file_uploader("Välj en bild", type=["jpg", "jpeg", "png"])

can_submit = bool(site_id.strip()) and (uploaded_file is not None)

if st.button("Spara bild i databasen", type="primary", disabled=not can_submit):
    try:
        # 1) Läs in bytes från uppladdad fil
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        if not file_bytes:
            st.error("Uppladdad fil verkar tom.")
            st.stop()

        # 2) Ladda upp till Azure Blob → få (image_uri, sas_url)
        # image_uri = permanent blob-URL (utan SAS) → sparas i DB
        # sas_url   = tillfällig visnings-URL (funkar med privat container)
        image_uri, sas_url = storage.save_image_bytes(
            site_id.strip(),
            file_bytes,
            original_name=uploaded_file.name,
        )

        # 3) INSERT i captures → få capture_id
        capture_id, captured_at = insert_capture(site_id.strip(), image_uri)

        # 4) Kör YOLO – skriv bytes till en tempfil så din predict kan läsa från path
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        detections = bs_model.predict_bins(yolo, tmp_path, conf=0.25)

        # 5) Bygg rader för bin_status
        ts_utc = datetime.now(timezone.utc)
        rows = []
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            rows.append({
                "ts_utc": ts_utc,
                "site_id": site_id.strip(),
                "bin_id": None,  # None i POC
                "klass": d["class_name"],
                "confidence": float(d["confidence"]),
                "bbox": json.dumps({"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}),
                "raw": json.dumps(d["raw"]),
                "capture_id": str(capture_id),
                "model_version": bs_model.MODEL_VERSION,
            })

        insert_predictions(rows)

        needs_empty = sum(1 for r in rows if r["klass"] in ("full", "overfull", "bin_full", "bin_overfull"))
        st.success(
            f"Bild + prediktioner sparade!\n\n"
            f"**site_id:** {site_id}  \n"
            f"**captured_at:** {captured_at}  \n"
            f"**Prediktioner:** {len(rows)} (Behöver tömmas: {needs_empty})"
        )

        # 6) Visa bilden via SAS-URL (eller image_uri om SAS saknas)
        st.image(sas_url or image_uri, caption="Uppladdad bild (Azure Blob)", use_container_width=True)

        # 7) Kvittorader
        with engine.begin() as conn:
            cc = conn.execute(text("SELECT COUNT(*) FROM captures")).scalar()
            pp = conn.execute(text("SELECT COUNT(*) FROM bin_status")).scalar()
        st.caption(f"[Upload] DB counts → captures={cc}, bin_status={pp}")

    except Exception as e:
        st.error(f"Något gick fel: {e}")



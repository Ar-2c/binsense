# binsense_app/pages/3_Ladda_upp_bild.py

import os
import json
import pathlib
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import text
from PIL import Image

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient, ContentSettings

from binsense.db import get_engine
from binsense import model as bs_model


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
load_dotenv()  # för DB_URL, AZURE_* om de ligger i .env

engine = get_engine()
st.caption(f"[Upload] DB: {engine.url}") # KOMMENTERA UT!

@st.cache_resource
def get_yolo():
    """Ladda YOLO en gång (cache)."""
    return bs_model.load_model()

yolo = get_yolo()


# -----------------------------
# Hjälpare
# -----------------------------
def upload_to_blob(site_id: str, uploaded_file) -> str | None:
    """
    Ladda upp till Azure Blob om AZURE_STORAGE_CONNECTION_STRING finns.
    Returnerar blob-URI eller None om ingen blob-konfig finns.
    """
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        return None

    container = os.getenv("AZURE_BLOB_CONTAINER", "images")
    bsc = BlobServiceClient.from_connection_string(conn_str)

    blob_name = (
        f"{site_id.strip()}/"
        f"{datetime.now(timezone.utc):%Y/%m/%d}/"
        f"{int(datetime.now(timezone.utc).timestamp())}_{uploaded_file.name}"
    )
    blob = bsc.get_blob_client(container=container, blob=blob_name)

    uploaded_file.seek(0)
    blob.upload_blob(
        uploaded_file.getvalue(),
        overwrite=True,
        content_settings=ContentSettings(content_type=uploaded_file.type or "image/jpeg"),
    )
    return f"https://{bsc.account_name}.blob.core.windows.net/{container}/{blob_name}"


def save_locally(site_id: str, uploaded_file) -> pathlib.Path:
    """Spara filen lokalt under data/uploads/<site_id>/ och returnera path."""
    uploaded_file.seek(0)
    folder = pathlib.Path("data/uploads") / site_id.strip()
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uploaded_file.name}"
    save_path = folder / filename
    with open(save_path, "wb") as f:
        f.write(uploaded_file.read())
    return save_path


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
        # 1) Spara lokalt (alltid, bra fallback)
        local_path = save_locally(site_id, uploaded_file)

        # 2) Försök ladda upp till Azure Blob → använd blob-URI om det funkar
        image_uri = upload_to_blob(site_id, uploaded_file) or str(local_path.as_posix())

        # 3) INSERT i captures → få capture_id
        capture_id, captured_at = insert_capture(site_id.strip(), image_uri)

        # 4) Kör YOLO på den lokala filen (snabbast/gemensamt)
        detections = bs_model.predict_bins(yolo, local_path, conf=0.25)

        # 5) Bygg rader för bin_status
        ts_utc = datetime.now(timezone.utc)
        rows = []
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            rows.append({
                "ts_utc": ts_utc,
                "site_id": site_id.strip(),
                "bin_id": None,  # kan vara None i POC
                "klass": d["class_name"],
                "confidence": float(d["confidence"]),
                "bbox": json.dumps({"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}),
                "raw": json.dumps(d["raw"]),
                "capture_id": str(capture_id),
                "model_version": bs_model.MODEL_VERSION,
            })

        insert_predictions(rows)

        needs_empty = sum(1 for r in rows if r["klass"] in ("full", "overfull"))
        st.success(
            f"Bild + prediktioner sparade!\n\n"
            f"**site_id:** {site_id}  \n"
            f"**captured_at:** {captured_at}  \n"
            f"**Prediktioner:** {len(rows)} (Behöver tömmas: {needs_empty})"
        )

        # Visa bilden (lokalt sparad) så man får direkt feedback
        try:
            st.image(str(local_path), caption="Uppladdad bild", use_container_width=True)
        except Exception:
            # fallback om Pillow knasar
            st.write(f"Bild sparad: {local_path}")

        # 6) DB-counts som kvitto
        with engine.begin() as conn:
            cc = conn.execute(text("SELECT COUNT(*) FROM captures")).scalar()
            pp = conn.execute(text("SELECT COUNT(*) FROM bin_status")).scalar()
        st.caption(f"[Upload] DB counts → captures={cc}, bin_status={pp}")

    except Exception as e:
        st.error(f"Något gick fel: {e}")


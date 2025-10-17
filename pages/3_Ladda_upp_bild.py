# binsense_app/pages/3_Ladda_upp_bild.py
import json
from binsense import model as bs_model
import streamlit as st
from sqlalchemy import create_engine, text
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import pathlib

@st.cache_resource
def get_yolo():
    return bs_model.load_model()   # laddar models/best.pt

yolo = get_yolo()                  # <-- använd 'yolo', inte 'model'

# --- Ladda miljövariabler / DB-anslutning ---
load_dotenv()  # bara om du har .env
DB_URL = os.getenv("DB_URL")

if not DB_URL:
    st.error("Kunde inte hitta DB_URL. Kontrollera din .env eller secrets.toml")
else:
    engine = create_engine(DB_URL)

def insert_capture(site_id: str, image_uri: str):
    """Skapar en rad i captures och returnerar (capture_id, captured_at_utc)."""
    captured_at_utc = datetime.now(timezone.utc)
    query = text("""
        INSERT INTO captures (site_id, image_uri, captured_at, source)
        VALUES (:site_id, :image_uri, :captured_at, 'mobile')
        RETURNING id
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "site_id": site_id,
            "image_uri": image_uri,
            "captured_at": captured_at_utc
        }).mappings().first()
    return row["id"], captured_at_utc

def require_login():
    if not st.session_state.get("user"):
        st.switch_page("app.py")

def sidebar_userbox():
    u = st.session_state.get("user", {})
    with st.sidebar:
        st.caption(f"Användare: {u.get('name','okänd')} • tenant {u.get('tenant_id','-')}")
        if st.button("Logga ut"):
            st.session_state.pop("user", None)
            st.experimental_rerun()

require_login()
sidebar_userbox()

st.set_page_config(page_title="Binsense – Ladda upp bild", layout="centered")
st.title("Ladda upp bild")

# försök riktig backend; annars enkel lokal fallback
try:
    from binsense import model, db
    from binsense import storage  # om ni har en adapter; annars fallback nedan
    HAS_BACKEND = True
except Exception:
    HAS_BACKEND = False

    class _Storage:
        def save_image_bytes(self, b: bytes, suffix=".jpg"):
            p = Path("data/images"); p.mkdir(parents=True, exist_ok=True)
            name = f"{uuid.uuid4().hex}{suffix}"
            fp = p / name
            fp.write_bytes(b)
            return str(fp)  # "uri"
        def fetch_for_inference(self, uri: str) -> str:
            return uri
    storage = _Storage()

    class _DB:
        def init(self): pass
        def insert_capture(self, site_id, image_uri, captured_at, source):
            return 1
        def insert_predictions(self, capture_id, preds): pass
    db = _DB()

    class _Model:
        def __call__(self): pass
    def get_model(*args, **kwargs): return _Model()
    def predict(m, path):
        import numpy as np
        img = np.zeros((50,50,3), dtype=np.uint8)
        preds = [{"class":"bin_half","conf":0.8,"fill_pct":50,"bbox_xyxy":[0,0,10,10]}]
        return img, preds
    model = type("M", (), {"get_model": staticmethod(get_model), "predict": staticmethod(predict)})

db.init()

# UI
site_id = st.text_input("Ange Site ID", placeholder="t.ex. site-001")
uploaded_file = st.file_uploader("Välj en bild", type=["jpg", "jpeg", "png"])

# Always render button, but disable until båda finns
can_submit = bool(site_id.strip()) and (uploaded_file is not None)
clicked = st.button("Spara bild i databasen", type="primary", disabled=not can_submit)

if clicked:
    try:
        # 1) Spara filen
        uploaded_file.seek(0)  # säkert ifall Streamlit läst den tidigare
        folder = pathlib.Path("data/uploads") / site_id.strip()
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uploaded_file.name}"
        save_path = folder / filename
        with open(save_path, "wb") as f:
            f.write(uploaded_file.read())

        image_uri = str(save_path.as_posix())

        # 2) INSERT i captures och hämta capture_id
        capture_id, captured_at = insert_capture(site_id.strip(), image_uri)

        #LÄGG IN HÄR! 
        
        # 3) Kör modellen (om du kopplat in binsense/model.py)
        detections = bs_model.predict_bins(yolo, save_path, conf=0.25)

        # 4) Bygg rader för bin_status (även om 0 detektioner)
        ts_utc = datetime.now(timezone.utc)
        rows = []
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            rows.append({
                "ts_utc": ts_utc,
                "site_id": site_id.strip(),
                "bin_id": None,
                "klass": d["class_name"],
                "confidence": float(d["confidence"]),
                "bbox": json.dumps({"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}),
                "raw": json.dumps(d["raw"]),
                "capture_id": str(capture_id),
                "model_version": bs_model.MODEL_VERSION,
            })

        if rows:
            insert_sql = text("""
                INSERT INTO bin_status
                  (ts_utc, site_id, bin_id, class, confidence, bbox_xyxy, raw, capture_id, model_version)
                VALUES
                  (:ts_utc, :site_id, :bin_id, :klass, :confidence, CAST(:bbox AS JSONB), CAST(:raw AS JSONB), :capture_id, :model_version)
            """)
            with engine.begin() as conn:
                conn.execute(insert_sql, rows)

        needs_empty = sum(1 for r in rows if r["klass"] in ("full", "overfull"))
        st.success(
            f"✅ Bild + prediktioner sparade!\n\n"
            f"**site_id:** {site_id}  \n"
            f"**captured_at:** {captured_at}  \n"
            f"**Prediktioner:** {len(rows)} (Behöver tömmas: {needs_empty})"
        )
        st.image(str(save_path), caption="Uppladdad bild", use_container_width=True)

    except Exception as e:
        st.error(f"Något gick fel: {e}")

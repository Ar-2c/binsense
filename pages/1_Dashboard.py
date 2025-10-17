import streamlit as st
import pandas as pd
from readonly_sql import fetch_site_snapshot # hämtar sidan som jag skapade istället för db

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

st.set_page_config(page_title="Binsense – Dashboard", layout="wide")
st.title("Dashboard")

# ta in db
try:
    from binsense import db
    HAS_BACKEND = True
except Exception:
    HAS_BACKEND = False
    class _MockDB:
        def init(self): pass
        def latest_site_snapshot(self):
            return [
                {"id": 1, "name": "Rum A", "address": "Gatan 1", "antal_karl": 3, "fill_pct": 62},
                {"id": 2, "name": "Rum B", "address": "Gatan 2", "antal_karl": 5, "fill_pct": 81},
            ]
    db = _MockDB()

from binsense.db import get_engine
from sqlalchemy import text
import streamlit as st

eng = get_engine()

if HAS_BACKEND:
    from sqlalchemy import text
    summary_sql = text("""
        WITH ranked AS (
            SELECT
                bs.site_id,
                bs.bin_id,
                bs.class,
                bs.ts_utc,
                ROW_NUMBER() OVER (
                    PARTITION BY bs.site_id, bs.bin_id
                    ORDER BY bs.ts_utc DESC
                ) AS rn
            FROM bin_status bs
        ),
        latest AS (
            SELECT *
            FROM ranked
            WHERE rn = 1
        )
        SELECT
            s.site_id AS id,
            s.name,
            COUNT(*)                                AS total_bins,
            SUM( (class IN ('full','overfull'))::int ) AS need_count,
            SUM( (class = 'human')::int )           AS human_count,
            MAX(ts_utc)                             AS last_pred_ts
        FROM latest l
        JOIN sites s ON s.site_id = l.site_id
        GROUP BY s.site_id, s.name
        ORDER BY s.site_id;
    """)

    with eng.begin() as conn:
        df = pd.read_sql(summary_sql, conn)

    # Om tabellen är tom första gången:
    if df.empty:
        st.info("Inga prediktioner ännu. Ladda upp en bild på sidan **Ladda upp bild**.")
else:
    # Fallback: behåll nuvarande mock-anrop
    rows = fetch_site_snapshot()
    df = pd.DataFrame(rows)

if df.empty:
    st.info("Inga sites hittades.")
else:
    # Metrik
    c1, c2, c3 = st.columns(3)
    c1.metric("Antal sites", len(df))
    c2.metric("Behöver tömmas (totalt)", int(df["need_count"].sum()))
    c3.metric("Människa detekterad (totalt)", int(df["human_count"].sum()))

    # X/Y-kolumn
    df["Behöver tömmas (X/Y)"] = (
        df["need_count"].astype(int).astype(str) + "/" + df["total_bins"].astype(int).astype(str)
    )

    if HAS_BACKEND and not df.empty and "last_pred_ts" in df.columns:
        # Gör en läsbar sträng; vi visar i UTC för enkelhet
        df["senast_uppdaterad"] = pd.to_datetime(df["last_pred_ts"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Visa
    st.dataframe(
    df.rename(columns={
        "name": "Rum/site",
        "total_bins": "Antal kärl",
        "fill_pct": "Fyllnadsgrad (%)",
        "need_count": "Behöver tömmas",
        "human_count": "Människa detekterad",
        "senast_uppdaterad": "Senast uppdaterad",
    })[["id", "Rum/site", "Antal kärl", "Behöver tömmas (X/Y)", "Fyllnadsgrad (%)", "Människa detekterad"] + (["Senast uppdaterad"] if "senast_uppdaterad" in df.columns else [])],
    use_container_width=True,
    hide_index=True,
    )

    # --- Snabb-navigering till detaljsidan ---
    st.subheader("Öppna site")

if not df.empty:
    # Gör en stabil mapping site_id(str) -> name
    ids = df["id"].astype(str)
    name_map = dict(zip(ids, df["name"]))

    selected = st.selectbox(
        "Välj site",
        options=ids.tolist(),
        format_func=lambda sid: f"{sid} – {name_map.get(sid, '')}",
    )

    if st.button("Gå till detaljvy"):
        st.query_params["site_id"] = selected
        st.switch_page("pages/2_Site_detalj.py")
else:
    st.info("Inga sites hittades.")

if not HAS_BACKEND:
    st.warning("Mock-läge: backend ej laddad – visar exempeldata.")

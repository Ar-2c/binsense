import streamlit as st
import pandas as pd
from readonly_sql import fetch_site_snapshot # hämtar sidan som jag skapade istället för db
from binsense.db import get_engine
from sqlalchemy import text

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

# --- DB & status ---

# HAS_BACKEND = True  # TA BORT?! eftersom jag raderade den längst ned.

eng = get_engine()
st.caption(f"[Dashboard] DB: {eng.url}")

# Små räknare så vi ser att det finns data
try:
    with eng.begin() as conn:
        dd = conn.execute(text("""
            SELECT
              (SELECT COUNT(*) FROM information_schema.tables
                 WHERE table_schema='public' AND table_name='captures')   AS has_cap_tbl,
              (SELECT COUNT(*) FROM information_schema.tables
                 WHERE table_schema='public' AND table_name='bin_status') AS has_pred_tbl,
              (SELECT COUNT(*) FROM captures)     AS captures_rows,
              (SELECT COUNT(*) FROM bin_status)   AS bin_rows
        """)).mappings().first()
    st.caption(f"[Dashboard] Tabeller OK? captures_tbl={dd['has_cap_tbl']} bin_status_tbl={dd['has_pred_tbl']} • Rader: captures={dd['captures_rows']} bin_status={dd['bin_rows']}")
except Exception as e:
    st.error(f"Kunde inte läsa DB: {e}")

# --- Summering: senaste capture per site ---
# Vi väljer senaste 'captured_at' per site från captures,
# joinar sedan bin_status på just det capture_id:t för att räkna antalet detektioner.
summary_sql = text("""
WITH latest_cap AS (
  SELECT site_id, MAX(captured_at) AS max_cap
  FROM captures
  GROUP BY site_id
),
cap_ids AS (
  SELECT c.site_id, c.id AS capture_id, c.captured_at
  FROM captures c
  JOIN latest_cap lc ON lc.site_id = c.site_id AND lc.max_cap = c.captured_at
),
bins AS (
  SELECT bs.site_id, bs.capture_id, bs.class
  FROM bin_status bs
  JOIN cap_ids c ON c.capture_id = bs.capture_id
)
SELECT
  COALESCE(s.site_id, c.site_id) AS id,
  COALESCE(s.name,    c.site_id) AS name,
  COALESCE(COUNT(b.class), 0)    AS total_bins,                         -- antal detektioner i senaste capture
  (COALESCE(SUM( (b.class IN ('full','overfull'))::int ), 0) > 0) AS need_bool, -- Ja/Nej: finns någon full/overfull?
  MAX(c.captured_at) AS last_pred_ts
FROM cap_ids c
LEFT JOIN bins b  ON b.capture_id = c.capture_id
LEFT JOIN sites s ON s.site_id = c.site_id
GROUP BY COALESCE(s.site_id, c.site_id), COALESCE(s.name, c.site_id)
ORDER BY id;
""")

with eng.begin() as conn:
    df = pd.read_sql(summary_sql, conn)

if df.empty:
    st.info("Inga prediktioner ännu. Ladda upp en bild på sidan **Ladda upp bild**.")
else:
    # Metrik
    c1, c2 = st.columns(2)
    c1.metric("Antal sites", len(df))
    c2.metric("Behöver tömmas (totalt)", int(df["need_bool"].sum()))

    # Gör kolumner trevliga
    df["Behöver tömmas"] = df["need_bool"].map({True: "Ja", False: "Nej"})
    df["Senast uppdaterad"] = pd.to_datetime(df["last_pred_ts"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Visa tabell — behåll bara vettiga kolumner
    show = df.rename(columns={
        "name": "Rum/site",
        "total_bins": "Antal kärl",
    })[["id", "Rum/site", "Antal kärl", "Behöver tömmas", "Senast uppdaterad"]]

    # Tar bort "id" vet ej om den kan behövas senare dock
    show = show.drop(columns=["id"])

    st.dataframe(show, use_container_width=True, hide_index=True)

    # --- Snabb-navigering till detaljsidan ---
    st.subheader("Öppna site")
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


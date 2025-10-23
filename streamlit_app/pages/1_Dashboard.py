# pages/1_Dashboard.py

import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime

from binsense.db import get_engine, fetch_dashboard_summary


# -------------------------------------------------
# Grundinställningar + auth
# -------------------------------------------------
st.set_page_config(page_title="Binsense – Dashboard", layout="wide")

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

st.title("Dashboard")

# -------------------------------------------------
# DB
# -------------------------------------------------
eng = get_engine()
st.caption(f"[Dashboard] DB: {eng.url}")

# -------------------------------------------------
# Dagens dispatch (uppdaterad: senaste 24 timmar)
# -------------------------------------------------
from sqlalchemy import text
import pandas as pd
from binsense.db import get_engine
 
eng = get_engine()
 
st.subheader("Dagens dispatch")
 
DISPATCH_SQL = text("""
SELECT 
  a.generated_at,
  a.site_id,
  COALESCE(s.name, a.site_id) AS site_name,
  a.reason,
  a.last_seen,
  a.confidence
FROM alerts_dispatch_site a
LEFT JOIN sites s ON s.site_id = a.site_id
-- visa senaste 24h (byt till ::date = current_date om du vill 'idag')
WHERE a.generated_at >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '24 hours'
ORDER BY a.generated_at DESC;
""")
 
with eng.begin() as cx:
    ddf = pd.read_sql(DISPATCH_SQL, cx)
 
if ddf.empty:
    st.success("Inga dispatch-alerts senaste 24h. 🎉")
else:
    # Tidsformat (visa svensk tid om du vill)
    for col in ("generated_at", "last_seen"):
        if pd.api.types.is_datetime64_any_dtype(ddf[col]):
            # Om timestampsen är tz-aware: konvertera till Stockholm
            try:
                ddf[col] = pd.to_datetime(ddf[col], utc=True).dt.tz_convert("Europe/Stockholm")
            except Exception:
                ddf[col] = pd.to_datetime(ddf[col])
 
    ddf_view = ddf.rename(columns={
        "site_name": "Site",
        "reason": "Orsak",
        "confidence": "Confidence",
        "generated_at": "Genererad",
        "last_seen": "Senast sedd",
    })[["Site", "Orsak", "Confidence", "Senast sedd", "Genererad"]]
 
    st.metric("Antal alerts (24h)", len(ddf))
    st.dataframe(ddf_view, use_container_width=True, hide_index=True)

# -------------------------------------------------
# Summering per site
# -------------------------------------------------
thr = st.slider(
    "Tröskel: andel fulla kärl som krävs för 'TÖM' (gäller summering per site)",
    min_value=0.0, max_value=1.0, value=0.90, step=0.05,
)

df = fetch_dashboard_summary(eng)

if df.empty:
    st.info("Inga prediktioner ännu. Ladda upp en bild på sidan **Ladda upp bild**.")
    st.stop()

# Normalisera NaN → robust rendering
df = df.copy()
df["full_count"]  = df["full_count"].fillna(0).astype(int)
df["total_bins"]  = df["total_bins"].fillna(0).astype(int)
df["full_ratio"]  = df["full_ratio"].fillna(0.0)
#df["last_pred_ts"] = pd.to_datetime(df["last_pred_ts"], errors="coerce")

# Beräkna flagga + X/Y + visningskolumner
df["need_flag"] = (df["full_ratio"] >= thr) & (df["total_bins"] > 0)
df["Behöver tömmas"] = df["need_flag"].map({True: "Ja", False: "Nej"})
df["Fyllnadsgrad"] = df["full_count"].astype(str) + "/" + df["total_bins"].astype(str)
# Gör datumen enhetliga och tz-säkra i ett svep
ts_utc = pd.to_datetime(df["last_pred_ts"], errors="coerce", utc=True)

df["Senast uppdaterad"] = ts_utc.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
df.loc[ts_utc.isna(), "Senast uppdaterad"] = "–"
#df["Senast uppdaterad"] = df["last_pred_ts"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S UTC")
#df.loc[df["last_pred_ts"].isna(), "Senast uppdaterad"] = "–"

# Metrik
c1, c2 = st.columns(2)
c1.metric("Antal sites", len(df))
c2.metric("Behöver tömmas (totalt)", int(df["need_flag"].sum()))

st.write("")  # lite luft

# -------------------------------------------------
# Render: “tabell” med klickbart namn + “Öppna”-knapp
# -------------------------------------------------
# --- Compact render: header + rows with only right-side button ---

WIDTHS = [1, 1, 1, 1, 1.0]  # Rum/site, X/Y, Behöver tömmas, Senast uppdaterad, Knapp

# Header
hc = st.columns(WIDTHS)
hc[0].markdown("**Rum/site**")
hc[1].markdown("**Fyllnadsgrad**")
hc[2].markdown("**Behöver tömmas**")
hc[3].markdown("**Senast uppdaterad**")
hc[4].markdown("**Visa**")

# Rows
for _, r in df.sort_values("name").iterrows():
    c = st.columns(WIDTHS)

    # text columns
    c[0].write(r["name"])
    c[1].write(r["Fyllnadsgrad"])
    c[2].write(r["Behöver tömmas"])
    c[3].write(r["Senast uppdaterad"])

    # right-hand button
    if c[4].button("Öppna", key=f"open_{r['id']}", use_container_width=True):
        site = str(r["id"])
        try:
            st.query_params.update(site_id=site)           # new API
        except Exception:
            st.experimental_set_query_params(site_id=site) # fallback
        st.session_state["site_from_dash"] = site
        st.switch_page("pages/2_Site_detalj.py")

    st.divider()  # thin separator between rows



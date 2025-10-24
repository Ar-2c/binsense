# pages/1_Dashboard.py

import pandas as pd
import streamlit as st
from sqlalchemy import text
from core.db import get_engine, fetch_dashboard_summary

# fliknamn
st.set_page_config(page_title="Binsense – Dashboard", layout="wide")

# sidinställningar och användaruppgifter
def require_login():
    if not st.session_state.get("user"):
        st.switch_page("app.py")

def sidebar_userbox():
    u = st.session_state.get("user", {})
    with st.sidebar:
        st.caption(f"användare{u.get('tenant_id',':')} {u.get('name','okänd')}")
        if st.button("Logga ut"):
            st.session_state.pop("user", None)
            st.experimental_rerun()

require_login()
sidebar_userbox()

st.title("Dashboard")

# DB
eng = get_engine()

# Dagens dispatch (visar om det har kommit två "tömningssignaler" i rad under 24 timmar.)
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
    st.success("Inga dispatch-alerts senaste 24h.")
else:
    for col in ("generated_at", "last_seen"):
        if pd.api.types.is_datetime64_any_dtype(ddf[col]):
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

# Slider för att justera tröskel för tömning.
thr = st.slider(
    "Tröskel: andel fulla kärl som krävs för 'TÖM' (gäller summering per site)",
    min_value=0.0, max_value=1.0, value=0.90, step=0.05,
)

df = fetch_dashboard_summary(eng)

if df.empty:
    st.info("Inga prediktioner ännu. Ladda upp en bild på sidan **Ladda upp bild**.")
    st.stop()

# Fyller saknade värden med noll.
df = df.copy()
df["full_count"]  = df["full_count"].fillna(0).astype(int)
df["total_bins"]  = df["total_bins"].fillna(0).astype(int)
df["full_ratio"]  = df["full_ratio"].fillna(0.0)

# Beräkna flagga + fyllnadsgrad/total bins + visningskolumner
df["need_flag"] = (df["full_ratio"] >= thr) & (df["total_bins"] > 0)
df["Behöver tömmas"] = df["need_flag"].map({True: "Ja", False: "Nej"})
df["Fyllnadsgrad"] = df["full_count"].astype(str) + "/" + df["total_bins"].astype(str)
# Gör datumen enhetliga
ts_utc = pd.to_datetime(df["last_pred_ts"], errors="coerce", utc=True)

df["Senast uppdaterad"] = ts_utc.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
df.loc[ts_utc.isna(), "Senast uppdaterad"] = "–"

# Summera antal sites och behöver tömmas
c1, c2 = st.columns(2)
c1.metric("Antal sites", len(df))
c2.metric("Behöver tömmas (totalt)", int(df["need_flag"].sum()))

st.write("") # mellanrum

# Tabell
WIDTHS = [1, 1, 1, 1, 1.0] # Möjlighet att justera kolumnbredd

# Rubriker
hc = st.columns(WIDTHS)
hc[0].markdown("**Rum/site**")
hc[1].markdown("**Fyllnadsgrad**")
hc[2].markdown("**Behöver tömmas**")
hc[3].markdown("**Senast uppdaterad**")
hc[4].markdown("**Visa**")

# Rader
for _, r in df.sort_values("name").iterrows():
    c = st.columns(WIDTHS)

    # textkolumner
    c[0].write(r["name"])
    c[1].write(r["Fyllnadsgrad"])
    c[2].write(r["Behöver tömmas"])
    c[3].write(r["Senast uppdaterad"])

    # Öppna-knapp
    if c[4].button("Öppna", key=f"open_{r['id']}", use_container_width=True):
        site = str(r["id"])
        try:
            st.query_params.update(site_id=site)
        except Exception:
            st.experimental_set_query_params(site_id=site) # fallback
        st.session_state["site_from_dash"] = site
        st.switch_page("pages/2_Site_detalj.py")

    st.divider()  # streck mellan rader



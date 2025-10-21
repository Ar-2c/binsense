import streamlit as st
import pandas as pd
from binsense.db import get_engine, fetch_dashboard_summary

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

eng = get_engine()
st.caption(f"[Dashboard] DB: {eng.url}")

# Global tröskel för "Behöver tömmas?"
thr = st.slider("Tröskel: andel fulla kärl som krävs för 'TÖM' (gäller summering per site)",
                min_value=0.0, max_value=1.0, value=0.90, step=0.05)

# Hämta summering per site
df = fetch_dashboard_summary(eng)

if df.empty:
    st.info("Inga prediktioner ännu. Ladda upp en bild på sidan **Ladda upp bild**.")
else:
    # Beräkna Ja/Nej + X/Y
    df["need_bool"] = (df["full_ratio"] >= thr) & (df["total_bins"] > 0)
    df["Behöver tömmas"] = df["need_bool"].map({True: "Ja", False: "Nej"})
    df["X/Y"] = df["full_count"].fillna(0).astype(int).astype(str) + "/" + df["total_bins"].fillna(0).astype(int).astype(str)
    df["Senast uppdaterad"] = pd.to_datetime(df["last_pred_ts"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Metrik
    c1, c2 = st.columns(2)
    c1.metric("Antal sites", len(df))
    c2.metric("Behöver tömmas (totalt)", int(df["need_bool"].sum()))

    # Visa tabell – behåll kolumner som är vettiga för översikt
    show = df.rename(columns={"name": "Rum/site"})[
        ["id", "Rum/site", "X/Y", "Behöver tömmas", "Senast uppdaterad"]
    ]
    # Vill du dölja "id" i vyn men ha kvar för navigation:
    st.dataframe(show.drop(columns=["id"]), use_container_width=True, hide_index=True)

    # --- Snabb-navigering till detaljsidan ---
    st.subheader("Öppna site")
    ids = df["id"].astype(str)
    name_map = dict(zip(ids, df["name"]))
    selected = st.selectbox("Välj site", options=ids.tolist(), format_func=lambda sid: f"{sid} – {name_map.get(sid, '')}")
    if st.button("Gå till detaljvy"):
        st.query_params["site_id"] = selected
        st.switch_page("pages/2_Site_detalj.py")

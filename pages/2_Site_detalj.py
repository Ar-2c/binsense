# pages/2_Site_detalj.py
from __future__ import annotations
import pandas as pd
import streamlit as st

from binsense.db import get_engine, fetch_sites, fetch_captures, fetch_predictions, fetch_history_per_capture
from binsense.storage import load_image_from_uri, sas_url_for
from binsense.viz import draw_boxes
from binsense.logic import room_needs_empty

# --- auth / sidebar ---
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

eng = get_engine()
st.caption(f"[Detalj] DB: {eng.url}")

# --- välj site ---
sites_df = fetch_sites(eng)
site_options = sites_df["site_id"].astype(str).tolist()
qp_site = st.query_params.get("site_id")
default_site = qp_site if qp_site in site_options else (site_options[0] if site_options else "")
site_id = st.selectbox("Välj site", site_options, index=(site_options.index(default_site) if default_site in site_options else 0))

if not site_id:
    st.info("Inga sites hittades."); st.stop()

# --- välj capture ---
caps = fetch_captures(site_id, limit=50, engine=eng)
if caps.empty:
    st.info("Inga bilder hittades för den här siten ännu."); st.stop()

def _cap_label(row):
    return f"{pd.to_datetime(row.captured_at).tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S UTC')}  •  id={row.capture_id}"

sel = st.selectbox("Välj bild (capture)", options=range(len(caps)), format_func=lambda i: _cap_label(caps.iloc[i]), index=0)
cap = caps.iloc[sel]
capture_id, image_uri, captured_at = cap.capture_id, cap.image_uri, cap.captured_at

preds = fetch_predictions(str(capture_id), engine=eng)

# --- layout ---
c1, c2 = st.columns([2, 1], gap="large")

with c1:
    st.subheader(f"Senaste bild – site {site_id}")
    st.caption(f"captured_at: {captured_at} • capture_id: {capture_id}")

    # 1) Hämta en visningsbar URL (SAS om containern är privat)
    view_url = sas_url_for(image_uri, hours=1)

    # 2) Ladda som PIL (så vi kan rita)
    img = load_image_from_uri(view_url)

    if img is None:
        # Om vi av någon anledning inte kunde läsa bytes → visa direkt-URL (utan boxes)
        st.warning("Kunde inte läsa bildbytes för ritning – visar URL direkt.")
        st.image(view_url, use_container_width=True)
    else:
        # 3) Rita boxes om det finns preds
        pred_rows = preds.to_dict("records")
        boxed = draw_boxes(img, pred_rows)
        st.image(boxed, caption="Senaste bild med markerade kärl", use_container_width=True)

with c2:
    st.subheader("Detektioner (senaste)")
    if preds.empty:
        st.info("Inga detektioner i senaste bilden.")
    else:
        show = preds.rename(columns={"class": "Klass", "confidence": "Confidence"})[["Klass", "Confidence"]]
        show["Confidence"] = (show["Confidence"].astype(float) * 100).round(0).astype(int).astype(str) + " %"
        st.dataframe(show, use_container_width=True, hide_index=True)

        thr = st.slider("Tröskel: andel fulla kärl som krävs för 'TÖM'", 0.0, 1.0, 0.90, 0.05)
        need, need_cnt, total, ratio = room_needs_empty(preds, threshold=thr)
        st.metric("Behöver tömmas?", "Ja" if need else "Nej",
                  delta=f"{need_cnt}/{total} kärl ({ratio:.0%}), tröskel {thr:.0%}")

# --- historik per bild (senaste 50) ---
st.subheader("Historik (senaste 50 bilder) – antal fulla / totalt")
hist = fetch_history_per_capture(site_id, limit=50, engine=eng)
if hist.empty:
    st.info("Ingen historik ännu.")
else:
    hist["Tid (UTC)"] = pd.to_datetime(hist["captured_at"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S")
    hist["andel"] = hist.apply(lambda r: (r["behov"]/r["total"]) if r["total"] else 0.0, axis=1)
    hist["X/Y"] = hist["behov"].astype(int).astype(str) + "/" + hist["total"].astype(int).astype(str)
    hist["Andel %"] = (hist["andel"] * 100).round(0).astype(int).astype(str) + " %"
    st.dataframe(hist[["Tid (UTC)", "capture_id", "X/Y", "Andel %"]], use_container_width=True, hide_index=True)
    st.caption("X = antal fulla/överfulla i bilden, Y = totala detekterade kärl i bilden.")

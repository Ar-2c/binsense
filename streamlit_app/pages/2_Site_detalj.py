# pages/2_Site_detalj.py
from __future__ import annotations
import pandas as pd
import streamlit as st
from core.db import get_engine
from core.queries import fetch_sites, fetch_captures, fetch_predictions, fetch_history_per_capture, delete_site
from core.storage import load_image_from_uri, sas_url_for, delete_site_blobs
from streamlit_app.viz import draw_boxes
from core.logic import room_needs_empty

# fliknamn
st.set_page_config(page_title="Binsense - detaljvy", layout="wide")

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

st.title("Detaljvy")

eng = get_engine()

# välj site
try:
    sites_df = fetch_sites(eng)
    if "site_id" not in sites_df.columns:
        st.error("Saknar kolumnen 'site_id' i sites-tabellen.")
        st.stop()
except Exception as e:
    st.error(f"Kunde inte hämta sites: {e}")
    st.stop()

site_options = sites_df["site_id"].astype(str).dropna().tolist()

if not site_options:
    st.info("Inga sites hittades.")
    st.stop()

# hanterar förval för "detaljvy" i rullistan 
def _qp(name: str):
    try:
        return st.query_params.get(name)
    except Exception:
        q = st.experimental_get_query_params().get(name, [None])
        return q[0] if isinstance(q, list) else q

pref = _qp("site_id") or st.session_state.get("site_from_dash")

# Hämtar vald site och sätter som default i rullistan
default_site = pref if pref in site_options else site_options[0]
try:
    default_idx = site_options.index(default_site)
except ValueError:
    default_idx = 0

site_id = st.selectbox("Välj site", site_options, index=default_idx)

# städa upp så den inte “fastnar” mellan sidbyten
st.session_state.pop("site_from_dash", None)

# välj bland tagna bilder
caps = fetch_captures(site_id, limit=50, engine=eng)
if caps.empty:
    st.info("Inga bilder hittades för den här siten ännu.")
    st.stop()

def _cap_label(row): # bildnamn
    return f"{pd.to_datetime(row.captured_at).tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S UTC')}  •  id={row.capture_id}"

sel = st.selectbox("Välj bild", options=range(len(caps)),
                   format_func=lambda i: _cap_label(caps.iloc[i]), index=0)
cap = caps.iloc[sel]
capture_id, image_uri, captured_at = cap.capture_id, cap.image_uri, cap.captured_at

preds = fetch_predictions(str(capture_id), engine=eng)

# layout
c1, c2 = st.columns([2, 1], gap="large")

with c1:
    st.subheader(f"Senaste bild – site {site_id}")
    st.caption(f"Bild tagen: {captured_at}")

    view_url = sas_url_for(image_uri, hours=1)
    img = load_image_from_uri(view_url)

    if img is None:
        st.warning("Kunde inte läsa bildbytes för ritning – visar URL direkt.")
        st.image(view_url, use_container_width=True)
    else:
        pred_rows = preds.to_dict("records")
        boxed = draw_boxes(img, pred_rows)
        st.image(boxed, caption="Senaste bild med markerade kärl", use_container_width=True)

with c2:
    st.subheader("Detektioner från senaste bilden")
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

# bildhistorik
st.subheader("Bildhistorik")
hist = fetch_history_per_capture(site_id, limit=50, engine=eng)
if hist.empty:
    st.info("Ingen historik ännu.")
else:
    hist["Tid (UTC)"] = pd.to_datetime(hist["captured_at"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S")
    hist["andel"] = hist.apply(lambda r: (r["behov"]/r["total"]) if r["total"] else 0.0, axis=1)
    hist["Fyllnadsgrad"] = hist["behov"].astype(int).astype(str) + "/" + hist["total"].astype(int).astype(str)
    hist["Andel %"] = (hist["andel"] * 100).round(0).astype(int).astype(str) + " %"
    st.dataframe(hist[["Tid (UTC)", "capture_id", "Fyllnadsgrad", "Andel %"]],
                 use_container_width=True, hide_index=True)

# delete
st.divider()
with st.expander("Radera site", expanded=False):
    st.warning(
        "Detta tar bort samtliga bilder för rummet och rader i databasen "
        f"för site **{site_id}**. Observera att detta är irreversibelt"
    )
    typed = st.text_input("Skriv exakt site-id för att bekräfta", "")
    col_a, col_b = st.columns([1, 3])
    can_delete = typed.strip() == str(site_id)

    if col_a.button("Radera permanent", type="primary", disabled=not can_delete):
        try:
            deleted_blobs = delete_site_blobs(site_id)
            engine = get_engine()
            counts = delete_site(engine, site_id)
            st.success(
                f"Raderat site {site_id}: "
                f"{deleted_blobs} blobbar • "
                f"bin_status={counts.get('bin_status',0)}, "
                f"captures={counts.get('captures',0)}, "
                f"alerts={counts.get('alerts',0)}, "
                f"sites={counts.get('sites',0)}"
            )
            try:
                st.query_params.update(site_id=None)
            except Exception:
                st.experimental_set_query_params()

            st.session_state.pop('site_from_dash', None)
            st.switch_page("pages/1_Dashboard.py")

        except Exception as e:
            st.error(f"Kunde inte radera: {e}")
    col_b.caption("Säkerhetslås: du måste skriva site-id exakt för att aktivera knappen.")

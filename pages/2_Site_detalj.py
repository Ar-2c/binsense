# binsense_app/pages/2_Site_detalj.py
import streamlit as st
import pandas as pd

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

st.set_page_config(page_title="Binsense – Site-detalj", layout="wide")
st.title("Site-detalj")

site_id = int(st.query_params.get("site_id", ["1"])[0])  # default 1
st.caption(f"Site ID: {site_id}")

# backend / mock
try:
    from binsense import db
    HAS_BACKEND = True
except Exception:
    HAS_BACKEND = False
    class _MockDB:
        def get_latest_capture(self, site_id):
            return {"id": 1, "site_id": site_id, "image_path":"https://via.placeholder.com/800",
                    "captured_at":"2025-10-15T12:00:00Z"}
        def get_predictions(self, cap_id):
            return [{"class":"bin_full","conf":0.92,"fill_pct":90},
                    {"class":"bin_half","conf":0.85,"fill_pct":50}]
        def get_history(self, site_id, limit=50):
            return [{"captured_at":f"2025-10-{d:02d}", "fill_pct": 50+d%40, "antal":3} for d in range(1,15)]
    db = _MockDB()

cap = db.get_latest_capture(site_id)
if not cap:
    st.info("Ingen data ännu för denna site.")
else:
    st.subheader("Senaste bild")
    st.image(cap.get("image_path") or cap.get("image_uri"), use_container_width=True, caption=cap["captured_at"])

    preds = db.get_predictions(cap["id"])
    st.subheader("Detaljvy för alla kärl (senaste)")
    st.dataframe(pd.DataFrame(preds), use_container_width=True, hide_index=True)

    st.subheader("Historik (fyllnadsgrad %)")
    hist = pd.DataFrame(db.get_history(site_id))
    if not hist.empty:
        hist = hist.set_index("captured_at")
        st.line_chart(hist[["fill_pct"]])
    else:
        st.write("Ingen historik än.")

if not HAS_BACKEND:
    st.warning("Mock-läge: backend ej laddad – visar exempeldata.")

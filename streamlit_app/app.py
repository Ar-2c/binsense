# binsense_app/app.py
from dotenv import load_dotenv, find_dotenv # fixen för azure_storage_connection
#load_dotenv(find_dotenv(usecwd=True))  # måste köras innan binsense.storage importeras
from datetime import datetime
import os, streamlit as st

load_dotenv(dotenv_path='.env')

# Mappa secrets till env så binsense.db fungerar
for key in ("DB_URL","DB_USER","DB_PASS","DB_HOST","DB_PORT","DB_NAME"):
    if key in st.secrets and key not in os.environ:
        os.environ[key] = str(st.secrets[key])

st.set_page_config(page_title="Binsense – Logga in", layout="wide")

# --- Dölj sidomeny + hamburgare just på denna sida ---
HIDE_SIDEBAR_CSS = """
    <style>
      [data-testid="stSidebar"] {display: none;}
      [data-testid="collapsedControl"] {display: none;}
    </style>
"""
st.markdown(HIDE_SIDEBAR_CSS, unsafe_allow_html=True)

# --- Om redan inloggad: hoppa direkt till Dashboard ---
if st.session_state.get("user"):
    st.switch_page("pages/1_Dashboard.py")

st.title("Logga in")

# === Enkelt auth-upplägg för POC ===
# 1) Antingen flera användare i st.secrets:
# [users]
# alice = "hemligt"
# bob = "banan"
#
# 2) Eller ett globalt lösenord:
# APP_PASSWORD = "binsense"
USERS = dict(st.secrets.get("users", {}))
GLOBAL_PWD = st.secrets.get("APP_PASSWORD")

st.markdown("<style>div[data-testid='stForm']{max-width:420px;margin:0 auto;}</style>", unsafe_allow_html=True)

with st.form("login", clear_on_submit=False, border=False):
    username = st.text_input("Användarnamn", value="")
    password = st.text_input("Lösenord", type="password", value="")
    login = st.form_submit_button("Logga in")   # lägg ev. use_container_width=False om du vill ha smalare knapp
    create_account = st.form_submit_button("Har du glömt lösenordet?")
    if create_account:
        st.write("Funktionen är under utveckling")


        

if login:
    ok = False
    if USERS:  # per-användare
        ok = USERS.get(username) == password
    elif GLOBAL_PWD:  # ett gemensamt lösen
        ok = (password == GLOBAL_PWD and username.strip() != "")
    else:
        # fallback för dev om man inte satt secrets ännu
        ok = (password == "binsense" and username.strip() != "")

    if ok:
        st.session_state["user"] = {
            "name": username.strip(),
            "login_at": datetime.utcnow().isoformat()
        }
        st.success("Inloggad! Tar dig vidare…")
        st.switch_page("pages/1_Dashboard.py")
    else:
        st.error("Fel användarnamn eller lösenord.")

# binsense_app/app.py
from dotenv import load_dotenv, find_dotenv
from datetime import datetime
import os, streamlit as st

load_dotenv(find_dotenv())

# Mappa secrets till env så core.db fungerar
for key in ("DB_URL","DB_USER","DB_PASS","DB_HOST","DB_PORT","DB_NAME"):
    if key in st.secrets and key not in os.environ:
        os.environ[key] = str(st.secrets[key])

st.set_page_config(page_title="Binsense – Logga in", layout="wide")

# döljer sidomenyn
HIDE_SIDEBAR_CSS = """
    <style>
      [data-testid="stSidebar"] {display: none;}
      [data-testid="collapsedControl"] {display: none;}
    </style>
"""
st.markdown(HIDE_SIDEBAR_CSS, unsafe_allow_html=True)

# Vid inloggning skickas användaren till Dashboard
if st.session_state.get("user"):
    st.switch_page("pages/1_Dashboard.py")

st.markdown("""
    <h1 style='text-align: center;'>Logga in</h1>
""", unsafe_allow_html=True)

# användar- och lösenordslogik
USERS = dict(st.secrets.get("users", {}))
GLOBAL_PWD = st.secrets.get("APP_PASSWORD")

st.markdown("<style>div[data-testid='stForm']{max-width:420px;margin:0 auto;}</style>", unsafe_allow_html=True)

# login
with st.form("login", clear_on_submit=False, border=False):
    username = st.text_input("Användarnamn", value="")
    password = st.text_input("Lösenord", type="password", value="")
    login = st.form_submit_button("Logga in")

if login:
    ok = False
    if USERS:
        ok = USERS.get(username) == password
    elif GLOBAL_PWD:
        ok = (password == GLOBAL_PWD and username.strip() != "")
    if ok:
        st.session_state["user"] = {
            "name": username.strip(),
            "login_at": datetime.utcnow().isoformat()
        }
        st.switch_page("pages/1_Dashboard.py")
    else:
        st.error("Fel användarnamn eller lösenord.")

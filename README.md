# Binsense POC
## Setup
```bash
git clone <repo-url>
cd binsense_app
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env     # fyll i DB_URL etc
streamlit run app.py
```

```
binsense_app/
├─ app.py
├─ pages/
│  ├─ 1_Dashboard.py        ← ✅ ska vara med
│  ├─ 2_Site_detalj.py
│  └─ 3_Ladda_upp_bild.py
├─ binsense/
│  ├─ db.py
│  ├─ logic.py
│  ├─ storage.py
│  └─ viz.py
├─ README.md
├─ requirements.txt
├─ .env.example
└─ .gitignore

```



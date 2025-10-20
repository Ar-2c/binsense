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
├─ app.py                          # landningssida / redirect till Dashboard
├─ pages/
│  ├─ 1_Dashboard.py
│  ├─ 2_Site_detalj.py
│  └─ 3_Ladda_upp_bild.py
├─ binsense/
│  ├─ __init__.py
│  ├─ db.py                        # DB-helper (init, queries)
│  ├─ model.py                     # YOLO-load & predict (cached)
│  ├─ schemas.py                   # dataklasser/helpers
│  └─ viz.py                       # plotting/helpers
├─ etl/
│  └─ daily_ingest.py              # ev. schemalagt flöde
├─ configs/
│  └─ app.toml                     # t.ex. sökvägar, klassnamn, HAS_BACKEND
├─ data/
│  ├─ images/                      # lokalt mock-läge
│  ├─ uploads/                     # sparade uploads (backend)
│  └─ results/                     # ev. plottade bilder
├─ models/
│  └─ best.pt                      # YOLO-vikt (valfritt, helst via LFS)
├─ requirements.txt
└─ README.md


```


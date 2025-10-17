\# Binsense POC
\## Setup
```bash
git clone <repo-url>
cd binsense\_app
python -m venv .venv
.venv\\Scripts\\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # fyll i DB\_URL etc

```
binsense\_app/
├─ app.py                     # landningssida / omdirigera till Dashboard
├─ pages/
│  ├─ 1\_Dashboard.py
│  ├─ 2\_Site\_detalj.py
│  └─ 3\_Ladda\_upp\_bild.py
├─ binsense/
│  ├─ db.py                   # SQLite helper (init, queries)
│  ├─ model.py                # YOLO-load \& predict (cached)
│  ├─ schemas.py              # dataklasser/helpers
│  └─ viz.py                  # små plotting/helpers
├─ etl/
│  └─ daily\_ingest.py         # valfritt schemalagt flöde
├─ configs/
│  └─ app.toml                # t.ex. sökvägar, klassnamn
├─ data/
│  ├─ images/                 # lagrade originalbilder
│  └─ results/                # ev. plottade bilder
└─ models/
&nbsp;  └─ best.pt                 # YOLO-vikter

```


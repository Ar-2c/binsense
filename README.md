# Binsense – Smart avfallsövervakning

**Binsense** är en Streamlit-baserad webbapplikation som kombinerar **AI-baserad bildanalys** och **databashantering** för att övervaka fyllnadsnivåer i sopkärl.  
Applikationen använder en tränad **YOLO-modell** för att analysera bilder och avgöra hur fulla kärlen är, och lagrar resultaten i en **PostgreSQL-databas på Azure**.

---

## Huvudfunktioner

- **Dashboard** – Visar en översikt över alla sites och deras senaste fyllnadsnivåer.  
- **Site-detalj** – Möjlighet att välja en specifik plats och se historik, status och senaste prediktioner.  
- **Ladda upp bild** – Tillåter användaren att ladda upp en bild från ett soprum.  
  Bilden analyseras av YOLO-modellen, och resultaten (objekt, fyllnadsgrad, sannolikhet m.m.) sparas i databasen.

---

## Arkitektur och teknik

|Komponent |Beskrivning |
|------------|-------------|
| **Frontend** | Streamlit |
| **Backend / logik** | Python, SQLAlchemy |
| **AI-modell** | Ultralytics YOLO (PyTorch) |
| **Databas** | Azure PostgreSQL |
| **Deploy** | Hugging Face Spaces (app) + Azure (databas) |

---

## Systemflöde

1. Användaren öppnar Streamlit-appen (t.ex. via Hugging Face Spaces).  
2. En bild på ett soprum laddas upp via appen.  
3. Applikationen laddar YOLO-modellen från vikten `best.pt` och kör bildanalysen.  
4. Prediktionerna (klass, bounding box, confidence, timestamp m.m.) sparas i Azure PostgreSQL.  
5. Resultaten visualiseras på dashboardsidan och kan filtreras per site.

---

## Installation och körning

### 1️ Klona projektet

## 2 Skapa virtuell miljö och installera beroenden
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 3 Konfigurera miljövariabler
Kopiera exempel-filen och fyll i din egen databas-URL:
```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
```

Exempel:
```bash
DB_URL=postgresql+psycopg2://<user>:<password>@<host>:<port>/<database>
```

## 4 Starta appen
```bash
streamlit run app.py
```
eller (om appen ligger i en undermapp):
```bash
PYTHONPATH=. streamlit run streamlit_app/app.py
```
## Projektträd
```
binsense_app/
├─ configs/                  # App-konfig, loggning
│  └─ logging_conf.py
├─ core/                     # Domänlogik & DB-access (importera via binsense_app.core.*)
│  ├─ db.py                  # get_engine(), db helpers
│  ├─ logic.py 
│  ├─ queries.py             # SQL-fragment/ORM-queries
│  └─ storage.py             # fil-/bloblagring
├─ dispatch/                 # Batch/cron, notifieringar, mail
│  ├─ dispatch_site.py
│  └─ mailer.py
├─ ml/                       # Modellhantering (YOLO mm.)
│  ├─ best.pt                # vikter
│  └─ model.py               # load_model(), DEFAULT_WEIGHTS, MODEL_VERSION
├─ streamlit_app/            # UI
│  ├─ app.py                 # huvudapp (körs med streamlit run)
│  ├─ viz.py                 # delade visualiseringsfunktioner
│  └─ pages/
│     ├─ 1_Dashboard.py
│     ├─ 2_Site_detailj.py
│     └─ 3_Ladda_upp_bild.py
├─ requirements.txt
└─ README.md
```
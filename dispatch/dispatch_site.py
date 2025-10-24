# etl/dispatch_site.py

from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy import text
from core.db import get_engine

# --- konfig ---
TAU = 0.8           # konfidens-tröskel
THRESHOLD = 0.8     # andel fulla kärl som krävs
SINCE_HOURS = 24    # tidsfönster i timmar

# --- SQL ---
SQL_FETCH = text("""
SELECT site_id, class, confidence, ts_utc
FROM bin_status
WHERE ts_utc >= :since
ORDER BY site_id, ts_utc ASC
""")

SQL_INSERT_SITE = text("""
INSERT INTO alerts_dispatch_site
  (generated_at, site_id, reason, last_seen, confidence)
VALUES
  (:generated_at, :site_id, :reason, :last_seen, :confidence)
""")

# --- helpers ---
def site_group_is_full(df_group: pd.DataFrame, tau: float = TAU, threshold: float = THRESHOLD):
    """
    Returnerar dict om andelen kärl i en grupp är fulla/överfulla med hög confidence.
    Grupp = site_id + tidskluster.
    """
    total = len(df_group)
    if total == 0:
        return None

    df_ok = df_group[
        df_group['class_norm'].isin(['full', 'overfull']) &
        (df_group['confidence'] >= tau)
    ]
    ratio = len(df_ok) / total

    if ratio >= threshold:
        last = df_group.sort_values("ts_utc").iloc[-1]
        return dict(
            reason='site_group_full',
            last_seen=last['ts_utc'],
            confidence=float(df_ok['confidence'].mean())
        )
    return None

def main():
    eng = get_engine()
    since = datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)

    # Hämta data
    with eng.begin() as cx:
        df = pd.read_sql(SQL_FETCH, cx, params={"since": since})

    if df.empty:
        return

    # Normalisera klassnamn
    df['class_norm'] = df['class'].str.replace('bin_', '', regex=False)

    # Skapa tidskluster
    df['ts_group'] = df['ts_utc'].dt.floor('1min')  # justera till '5min' vid behov

    alerts = []
    for (site_id, ts_group), g in df.groupby(['site_id', 'ts_group']):
        res = site_group_is_full(g, tau=TAU, threshold=THRESHOLD)
        if res:
            alerts.append({
                'generated_at': datetime.now(timezone.utc),
                'site_id': str(site_id),
                'reason': res['reason'],
                'last_seen': res['last_seen'],
                'confidence': res['confidence']
            })

    if not alerts:
        return

    with eng.begin() as cx:
        cx.execute(SQL_INSERT_SITE, alerts)

if __name__ == '__main__':
    main()
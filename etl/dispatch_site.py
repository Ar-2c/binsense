# etl/dispatch_site.py

from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy import text
from binsense.db import get_engine
from binsense.logging_conf import setup_logging, get_logger, new_run_id

# --- konfig ---
TAU = 0.8           # konfidens-tröskel
SINCE_HOURS = 24    # tidsfönster i timmar

# --- logging ---
setup_logging(app_name='dispatch-site', to_file=True)
log = get_logger(__name__, tenant='demo')
RUN_ID = new_run_id()

# --- SQL ---
SQL_FETCH = text("""
SELECT site_id, class, confidence, ts_utc
FROM bin_status
WHERE ts_utc >= :since
ORDER BY site_id, ts_utc ASC
""")

SQL_INSERT_SITE = text("""
INSERT INTO alerts_dispatch_site
  (generated_at, site_id, reason, last_seen, confidence, run_id)
VALUES
  (:generated_at, :site_id, :reason, :last_seen, :confidence, :run_id)
""")
# Om du skapat UNIQUE-index (site_id, reason, last_seen), använd gärna:
# ... ON CONFLICT DO NOTHING

# --- helpers ---
def normalize_class(x: str) -> str:
    """
    Normaliserar klassnamn till {empty, half, full, overfull, human, ...}
    Ex: 'bin_overfull' -> 'overfull', 'Bin_Full ' -> 'full'
    """
    s = str(x).strip().lower()
    # ta bort ev. prefix före sista '_'
    if "_" in s:
        s = s.split("_")[-1]
    # synonymer (lägg till vid behov)
    aliases = {
        "overfilled": "overfull",
        "overflow": "overfull",
        "occupied": "full",
    }
    return aliases.get(s, s)

def two_in_a_row_full_site(df_site: pd.DataFrame, tau: float = TAU):
    """
    Returnerar dict om de TVÅ senaste obs på en site är full/overfull med min(conf) >= tau.
    Annars None.
    """
    if len(df_site) < 2:
        return None
    last2 = df_site.tail(2)
    classes = last2['class_norm'].tolist()
    classes_ok = all(c in ('full', 'overfull') for c in classes)
    conf_ok = float(last2['confidence'].min()) >= tau
    if classes_ok and conf_ok:
        last = last2.iloc[-1]
        return dict(
            reason='site_two_in_a_row_full',
            last_seen=last['ts_utc'],
            confidence=float(last['confidence'])
        )
    return None

def main():
    eng = get_engine()
    since = datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)

    # Hämta data
    with eng.begin() as cx:
        df = pd.read_sql(SQL_FETCH, cx, params={"since": since})

    if df.empty:
        log.info('Inga statusposter i fönstret', extra={"run_id": RUN_ID})
        return

    # Normalisera klass
    df['class_norm'] = df['class'].apply(normalize_class)

    alerts = []
    for site_id, g in df.groupby("site_id", sort=False):
        g = g.sort_values("ts_utc")
        res = two_in_a_row_full_site(g, tau=TAU)
        if res:
            alerts.append({
                'generated_at': datetime.now(timezone.utc),
                'site_id': str(site_id),
                'reason': res['reason'],
                'last_seen': res['last_seen'],
                'confidence': res['confidence'],
                'run_id': RUN_ID
            })
            log.info('Alert (site)', extra={'run_id': RUN_ID, 'site_id': site_id})
        else:
            # diagnostik: visa de två senaste för siten
            tail = g.tail(2)
            log.info(
                'Skip site',
                extra={
                    'run_id': RUN_ID,
                    'site_id': site_id,
                    'classes': tail['class_norm'].tolist(),
                    'conf_min': float(tail['confidence'].min())
                }
            )

    if not alerts:
        log.info('Inga alerts genererade', extra={'run_id': RUN_ID})
        return

    with eng.begin() as cx:
        cx.execute(SQL_INSERT_SITE, alerts)
    log.info('Alerts skrivna', extra={'run_id': RUN_ID, 'count': len(alerts)})

if __name__ == '__main__':
    main()
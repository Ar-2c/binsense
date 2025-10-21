from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy import text
from binsense.db import get_engine
from binsense.logging_conf import setup_logging, get_logger, new_run_id

setup_logging(app_name='dispatch-local', to_file=True)
log = get_logger(__name__, tenant='demo')
RUN_ID = new_run_id()

TAU = 0.8 # Konfidens tröskel
SINCE_HOURS = 24

SQL_FETCH = text("""
SELECT site_id, bin_id, class, confidence, ts_utc
FROM bin_status
WHERE ts_utc >= :since
ORDER BY site_id, bin_id, ts_utc ASC
""")

SQL_INSERT = text("""
INSERT INTO alerts_dispatch (generated_at, site_id, bin_id, reason, last_seen, confidence, run_id)
VALUES (:generated_at, :site_id, :bin_id, :reason, :last_seen, :confidence, :run_id)
""")

def two_in_a_row_full(df_bin, tau=TAU):
    if len(df_bin) < 2:
        return None
    last_two = df_bin.tail(2)
    classes_ok = all(c in ('full', 'overfull') for c in last_two['class'])
    conf_ok = float(last_two['confidence'].min()) >= tau
    if classes_ok and conf_ok:
        last = last_two.iloc[-1]
        return dict(reason='twotwo_in_a_row_full', last_seen=last['ts_utc'], confidence=float(last['confidence']))
    return None

def main():
    eng = get_engine()
    since = datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)
    with eng.begin() as cx:
        df = pd.read_sql(SQL_FETCH, cx, params={"since": since})
    if df.empty:
        log.info('Inga statusposter senaste 24h', extra={"run_id": RUN_ID})
        return
    
    alerts = []
    for (site_id, bin_id), g in df.groupby(["site_id", "bin_id"]):
        res = two_in_a_row_full(g)
        if res:
            alerts.append({
                'generated_at': datetime.now(timezone.utc),
                'site_id': site_id,
                'bin_id': bin_id,
                'reason': res['reason'],
                'last_seen': res['last_seen'],
                'confidence': res['confidence'],
                'run_id': RUN_ID
            })
            log.info('Alert', extra={'run_id': RUN_ID, 'site_id': site_id, 'bin_id': bin_id})

        if not alerts:
            log.info('Inga alerts', extra={'run_id': RUN_ID})
            return
        
        with eng.begin() as cx:
            cx.execute(SQL_INSERT, alerts)
        log.info('Alerts skrivna', extra={'run_id': RUN_ID, 'count': len(alerts)})

if __name__ == '__main__':
    main()
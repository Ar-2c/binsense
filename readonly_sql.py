# binsense_app/readonly_sql.py
from sqlalchemy import text
from binsense.db import get_engine  # ny import

_engine = None

def _eng():
    global _engine
    if _engine is None:
        _engine = get_engine()      # delad engine
    return _engine

# Klass -> procent (för medelvärden) och binärt
CLASS_TO_PERCENT = """
CASE LOWER(COALESCE(ls.class,''))
  WHEN 'empty'     THEN 0
  WHEN 'half'      THEN 50
  WHEN 'full'      THEN 90
  WHEN 'overfull'  THEN 110
  WHEN 'unknown'   THEN NULL
  WHEN 'human'     THEN NULL
  ELSE NULL
END
"""

NEED_EMPTY_CASE = """
CASE
  WHEN LOWER(COALESCE(ls.class,'')) IN ('full','overfull') THEN TRUE
  ELSE FALSE
END
"""

def fetch_site_snapshot():
    """
    [{id, name, total_bins, fill_pct, need_count, human_count}]
    """
    sql = f"""
    SELECT
      s.site_id                                 AS id,
      s.name                                    AS name,
      COUNT(b.bin_id)                           AS total_bins,
      COALESCE(ROUND(AVG({CLASS_TO_PERCENT})),0)::int AS fill_pct,
      COALESCE(SUM(CASE WHEN {NEED_EMPTY_CASE} THEN 1 ELSE 0 END),0)::int AS need_count,
      COALESCE(SUM(CASE WHEN LOWER(COALESCE(ls.class,''))='human' THEN 1 ELSE 0 END),0)::int AS human_count
    FROM sites s
    LEFT JOIN bins b ON b.site_id = s.site_id
    LEFT JOIN LATERAL (
        SELECT bs2.*
        FROM bin_status bs2
        WHERE bs2.bin_id = b.bin_id
        ORDER BY bs2.ts_utc DESC
        LIMIT 1
    ) ls ON TRUE
    GROUP BY s.site_id, s.name
    ORDER BY s.name;
    """
    with _eng().begin() as con:
        return [dict(r) for r in con.execute(text(sql)).mappings().all()]

def fetch_bins_latest(site_id: str | int):
    """
    [{bin_id, label, percent, need_empty, human_flag, class, confidence, captured_at}]
    """
    sql = f"""
    SELECT
      b.bin_id,
      b.label,
      ls.ts_utc AS captured_at,
      LOWER(COALESCE(ls.class,'')) = 'human' AS human_flag,
      {CLASS_TO_PERCENT}::numeric             AS percent,
      {NEED_EMPTY_CASE}                       AS need_empty,
      ls.class,
      ls.confidence
    FROM bins b
    LEFT JOIN LATERAL (
        SELECT bs2.*
        FROM bin_status bs2
        WHERE bs2.bin_id = b.bin_id
        ORDER BY bs2.ts_utc DESC
        LIMIT 1
    ) ls ON TRUE
    WHERE b.site_id = :sid
    ORDER BY b.bin_id;
    """
    with _eng().begin() as con:
        return [dict(r) for r in con.execute(text(sql), {"sid": str(site_id)}).mappings().all()]

def fetch_site_history(site_id: str | int, limit: int = 50):
    """
    Tidsserie med medel% och antal som behöver tömmas.
    """
    sql = f"""
    SELECT
      bs.ts_utc AS captured_at,
      ROUND(AVG(
        CASE LOWER(COALESCE(bs.class,''))
          WHEN 'empty'     THEN 0
          WHEN 'half'      THEN 50
          WHEN 'full'      THEN 90
          WHEN 'overfull'  THEN 110
          ELSE NULL
        END
      ))::int AS fill_pct,
      SUM(CASE WHEN LOWER(COALESCE(bs.class,'')) IN ('full','overfull') THEN 1 ELSE 0 END)::int AS need_count
    FROM bins b
    JOIN bin_status bs ON bs.bin_id = b.bin_id
    WHERE b.site_id = :sid
    GROUP BY bs.ts_utc
    ORDER BY bs.ts_utc DESC
    LIMIT :lim;
    """
    with _eng().begin() as con:
        return [dict(r) for r in con.execute(text(sql), {"sid": str(site_id), "lim": limit}).mappings().all()]

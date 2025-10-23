# binsense/db.py
from __future__ import annotations

import os
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ======================================
# Central DB-anslutning (oförändrad)
# ======================================
_engine: Engine | None = None

def get_engine() -> Engine:
    """Läs DB_URL från .env / secrets och cache:a engine."""
    global _engine
    if _engine is not None:
        return _engine

    # 1) försök via env
    db_url = os.getenv("DB_URL")
    # 2) fallback: streamlit secrets (om du använder det)
    if not db_url:
        try:
            import streamlit as st  # type: ignore
            db_url = st.secrets.get("DB_URL")  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            db_url = None

    if not db_url:
        raise RuntimeError("DB_URL saknas – sätt den i .env eller i Streamlit secrets.")

    _engine = create_engine(db_url)
    return _engine


# ======================================
# Konstanter för återanvändning
# ======================================
NEED_CLASSES_SQL = "('full','overfull','bin_full','bin_overfull')"


# ======================================
# Nya, “rena” helpers (föredragna)
# ======================================
def fetch_sites(engine: Optional[Engine] = None) -> pd.DataFrame:
    """Returnerar DataFrame med DISTINCT site_id som har captures."""
    eng = engine or get_engine()
    with eng.begin() as conn:
        df = pd.read_sql(text("SELECT DISTINCT site_id FROM captures ORDER BY site_id"), conn)
    return df

def fetch_captures(site_id: str, limit: int = 50, engine: Optional[Engine] = None) -> pd.DataFrame:
    """Returnerar senaste 'limit' captures för en site."""
    eng = engine or get_engine()
    with eng.begin() as conn:
        df = pd.read_sql(
            text("""
                SELECT id AS capture_id, image_uri, captured_at
                FROM captures
                WHERE site_id = :sid
                ORDER BY captured_at DESC
                LIMIT :lim
            """),
            conn,
            params={"sid": site_id, "lim": limit},
        )
    return df

def fetch_predictions(capture_id: str, engine: Optional[Engine] = None) -> pd.DataFrame:
    """Returnerar prediktioner för ett givet capture_id (senaste ordning efter confidence)."""
    eng = engine or get_engine()
    with eng.begin() as conn:
        df = pd.read_sql(
            text("""
                SELECT class, confidence, bbox_xyxy, raw
                FROM bin_status
                WHERE capture_id = :cid
                ORDER BY confidence DESC
            """),
            conn,
            params={"cid": str(capture_id)},
        )
    return df

def fetch_history_per_capture(site_id: str, limit: int = 50, engine: Optional[Engine] = None) -> pd.DataFrame:
    """
    Historik per bild (capture) – senaste N bilder med X/Y (fulla/överfulla vs total).
    """
    eng = engine or get_engine()
    with eng.begin() as conn:
        df = pd.read_sql(
            text(f"""
                SELECT
                  b.capture_id,
                  c.captured_at,
                  SUM((b.class IN {NEED_CLASSES_SQL})::int) AS behov,
                  COUNT(*) AS total
                FROM bin_status b
                JOIN captures c ON c.id = b.capture_id
                WHERE b.site_id = :sid
                GROUP BY b.capture_id, c.captured_at
                ORDER BY c.captured_at DESC
                LIMIT :lim
            """),
            conn,
            params={"sid": site_id, "lim": limit},
        )
    return df


# ======================================
# Gamla namn (bakåtkompatibla wrappers)
# – dessa finns kvar så övrig kod inte bryts
# ======================================
def fetch_site_ids() -> list[str]:
    """Legacy: returnerar lista[str] av site_id."""
    df = fetch_sites()
    return df["site_id"].astype(str).tolist()

def fetch_captures_for_site(site_id: str, limit: int = 50) -> pd.DataFrame:
    """Legacy wrapper för fetch_captures()."""
    return fetch_captures(site_id=site_id, limit=limit)

def fetch_predictions_for_capture(capture_id: str) -> pd.DataFrame:
    """Legacy wrapper för fetch_predictions()."""
    return fetch_predictions(capture_id=str(capture_id))

def fetch_daily_full_vs_total(site_id: str, days: int = 30) -> pd.DataFrame:
    """
    Legacy: behålls om något UI använder den.
    (Notera: den här räknar per minut-limit; i praktiken använder ni nu fetch_history_per_capture.)
    """
    eng = get_engine()
    with eng.begin() as conn:
        df = pd.read_sql(
            text("""
                SELECT
                  date_trunc('minute', ts_utc) AS ts_min,
                  SUM((class IN ('full','overfull'))::int) AS full_count,
                  COUNT(*) AS total_count
                FROM bin_status
                WHERE site_id = :sid
                GROUP BY 1
                ORDER BY 1 DESC
                LIMIT :lim
            """),
            conn,
            params={"sid": site_id, "lim": days * 48},  # grov limit
        )
    return df

def fetch_dashboard_summary(engine: Optional[Engine] = None) -> pd.DataFrame:
    """
    Summering per site baserat på senaste capture.
    Returnerar kolumner: id, name, total_bins, full_count, full_ratio, last_pred_ts
    """
    eng = engine or get_engine()
    with eng.begin() as conn:
        df = pd.read_sql(
            text(f"""
                WITH latest_cap AS (
                  SELECT site_id, MAX(captured_at) AS max_cap
                  FROM captures
                  GROUP BY site_id
                ),
                cap_ids AS (
                  SELECT c.site_id, c.id AS capture_id, c.captured_at
                  FROM captures c
                  JOIN latest_cap lc ON lc.site_id = c.site_id AND lc.max_cap = c.captured_at
                ),
                bins AS (
                  SELECT bs.site_id, bs.capture_id, bs.class
                  FROM bin_status bs
                  JOIN cap_ids c ON c.capture_id = bs.capture_id
                )
                SELECT
                  COALESCE(s.site_id, c.site_id) AS id,
                  COALESCE(s.name,    c.site_id) AS name,
                  COUNT(b.class)                    AS total_bins,
                  SUM( (b.class IN {NEED_CLASSES_SQL})::int ) AS full_count,
                  CASE WHEN COUNT(b.class) > 0
                       THEN SUM( (b.class IN {NEED_CLASSES_SQL})::int )::float / COUNT(b.class)
                       ELSE 0.0 END                AS full_ratio,
                  MAX(c.captured_at)               AS last_pred_ts
                FROM cap_ids c
                LEFT JOIN bins  b ON b.capture_id = c.capture_id
                LEFT JOIN sites s ON s.site_id    = c.site_id
                GROUP BY COALESCE(s.site_id, c.site_id), COALESCE(s.name, c.site_id)
                ORDER BY id;
            """),
            conn,
        )
    return df

def delete_site(engine, site_id: str) -> dict:
    """
    Tar bort all data kopplad till en site (inkl. alerts, status, captures, och site-rad).
    Returnerar antal rader som raderats per tabell.
    """
    counts = {}
    with engine.begin() as cx:
        # Kör i rätt ordning pga foreign keys
        for table in ["alerts_dispatch_site", "bin_status", "captures", "sites"]:
            try:
                result = cx.execute(
                    text(f"DELETE FROM {table} WHERE site_id = :sid"),
                    {"sid": site_id},
                )
                counts[table if table != "alerts_dispatch_site" else "alerts"] = result.rowcount
            except Exception as e:
                print(f"⚠️ Kunde inte radera i {table}: {e}")
                counts[table] = 0
    return counts
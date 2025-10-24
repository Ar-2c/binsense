# core/db.py
from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# skapar db koppling
_engine: Engine | None = None

def get_engine() -> Engine:
    """Läs DB_URL från .env / secrets och cache:a engine."""
    global _engine
    if _engine is not None:
        return _engine

    # försök via env
    db_url = os.getenv("DB_URL")
    # om .env inte skulle hittas läses secrets
    if not db_url:
        try:
            import streamlit as st
            db_url = st.secrets.get("DB_URL")
        except Exception:
            db_url = None

    if not db_url:
        raise RuntimeError("DB_URL saknas – sätt den i .env eller i Streamlit secrets.")

    _engine = create_engine(db_url)
    return _engine
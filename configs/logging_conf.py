# configs/logging_conf.py
import logging
import os
import uuid
from logging.handlers import TimedRotatingFileHandler

class _ContextFilter(logging.Filter):
    def filter(self, record):
        for k in ("tenant", "site_id", "bin_id", "run_id"):
            if not hasattr(record, k):
                setattr(record, k, "-")
        return True

_FMT = "[%(asctime)s][%(name)s][%(levelname)s]" \
       "[tenant=%(tenant)s site=%(site_id)s bin=%(bin_id)s run=%(run_id)s] %(message)s"

def setup_logging(
    app_name: str,
    level: str | None = None,
    to_file: bool = False,
    logs_dir: str = "logs",
):
    """
    Kör en gång per process (t.ex. i app.py eller i Function __init__).
    - app_name används för ev. filnamn.
    - to_file=True lokalt (roterar dagligen). I Azure Functions: lämna False.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    logging.captureWarnings(True)  # warnings

    lvl = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    root.setLevel(lvl)
    root.addFilter(_ContextFilter())

    # Console / stdout
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(_FMT))
    root.addHandler(ch)

    # Lokal fil med rotation
    if to_file:
        os.makedirs(logs_dir, exist_ok=True)
        fh = TimedRotatingFileHandler(
            os.path.join(logs_dir, f"{app_name}.log"),
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(_FMT))
        root.addHandler(fh)

def get_logger(name: str, **context) -> logging.LoggerAdapter:
    """Använd: get_logger(__name__, tenant='demo', site_id='site-01', run_id=run_id)"""
    return logging.LoggerAdapter(logging.getLogger(name), extra=context)

def new_run_id() -> str:
    return uuid.uuid4().hex[:12]
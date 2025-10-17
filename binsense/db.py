# db.py
import os
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DB_URL")

if not db_url:
    db_url = URL.create(
        drivername='postgresql+psycopg',
        username=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        host=os.getenv('DB_HOST'),
        port=(int(os.getenv('DB_PORT', '5432'))),
        database=os.getenv('DB_NAME', 'binsense'),
        query={"sslmode": "require"},
)

# Global engine    
_engine = create_engine(db_url, pool_pre_ping=True, future=True)

# Session factory
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)

def get_engine():
    """Return shared SQLAlchemy Engine."""
    return _engine

def get_session():
    """Create new Session. Use 'with' for automatic closing."""
    return SessionLocal()
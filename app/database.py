"""
Database engine + session setup.

Uses SQLite by default (zero-config, file-based, survives restarts as long as the
volume/disk persists) which is the right trade-off for a 3-hour take-home per the
prompt's own guidance ("SQLite over Postgres" is an explicitly sanctioned shortcut).

Swapping to Postgres later is a one-line change: set DATABASE_URL to a
postgresql+psycopg2:// URL and `pip install psycopg2-binary`. Nothing else in the
codebase is SQLite-specific (no raw SQL, pure SQLAlchemy ORM).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/patients.db")

# Make sure ./data exists so SQLite doesn't fail on first run.
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

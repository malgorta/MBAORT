import os
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# Database file location (relative to repository root)
DATA_DIR = Path(os.environ.get("DB_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "app.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

# Engine and session
# For SQLite in a single-threaded Streamlit app set check_same_thread
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db(create_folder: bool = True):
    """Create database file and tables.

    - Ensures `data/` directory exists (unless `create_folder` is False).
    - Imports models (so they are registered on `Base`) and creates tables.
    """
    if create_folder:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Import models to ensure they are registered on Base.metadata
    try:
        # Local import to avoid top-level circular imports
        from . import models  # noqa: F401
    except Exception:
        # If models fail to import, raise to let caller handle
        raise

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Yield a SQLAlchemy session and ensure it's closed.

    Usage:
        with get_session() as session:
            ...
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

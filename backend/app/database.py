import os
import time
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

Base = declarative_base()

def init_db_engine():
    db_url = settings.get_database_url()
    is_postgres = "postgresql" in db_url
    
    if is_postgres:
        retries = 8
        for attempt in range(1, retries + 1):
            try:
                eng = create_engine(
                    db_url,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 3}
                )
                with eng.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print(f"Successfully connected to PostgreSQL at: {settings.POSTGRES_SERVER} (attempt {attempt})")
                return eng
            except Exception as e:
                print(f"PostgreSQL connection attempt {attempt}/{retries} failed ({e}). Retrying in 2s...")
                time.sleep(2)
        print("All PostgreSQL connection attempts failed. Falling back to local SQLite database.")

    # Shared SQLite fallback: store in DOWNLOAD_DIR so all containers share it
    download_dir = settings.DOWNLOAD_DIR if os.path.exists(settings.DOWNLOAD_DIR) else "."
    sqlite_file = os.path.join(download_dir, "downloader.db")
    print(f"Using SQLite database at: {sqlite_file}")
    eng = create_engine(
        f"sqlite:///{sqlite_file}",
        connect_args={"check_same_thread": False}
    )
    return eng

engine = init_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure tables exist in both PostgreSQL and SQLite
try:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Base.metadata.create_all note: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

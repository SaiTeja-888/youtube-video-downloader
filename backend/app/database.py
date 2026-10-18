from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Attempt to connect to PostgreSQL. If it fails or is unavailable,
# we gracefully fall back to a local SQLite database for lightweight local development.
db_url = settings.get_database_url()
try:
    # Set a short timeout for health check
    engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 3} if "postgresql" in db_url else {})
    # Verify connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print(f"Successfully connected to PostgreSQL at: {settings.POSTGRES_SERVER}")
except Exception as e:
    print(f"PostgreSQL connection failed ({e}). Falling back to local SQLite database 'downloader.db'.")
    engine = create_engine(
        "sqlite:///downloader.db",
        connect_args={"check_same_thread": False}  # Needed only for sqlite multi-threading
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

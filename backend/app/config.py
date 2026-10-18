import os
import json
from pydantic_settings import BaseSettings
from pydantic import Field

# Ensure backend directory is in PATH so that local ffmpeg.exe and ffprobe.exe are always accessible
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = backend_dir + os.pathsep + os.environ.get("PATH", "")

class Settings(BaseSettings):
    PROJECT_NAME: str = "POSTLINK media downloader API"
    API_V1_STR: str = "/api"
    
    # Security
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production-123456", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # CORS
    BACKEND_CORS_ORIGINS: str = Field(
        default=(
            "http://localhost:3000,"
            "http://127.0.0.1:3000,"
            "http://localhost:3001,"
            "http://127.0.0.1:3001,"
            "http://localhost:80,"
            "http://localhost"
        ),
        env="BACKEND_CORS_ORIGINS",
    )
    BACKEND_CORS_ORIGIN_REGEX: str | None = Field(
        default=r"https://.*\.vercel\.app",
        env="BACKEND_CORS_ORIGIN_REGEX",
    )

    # Postgres Database
    POSTGRES_SERVER: str = Field(default="localhost", env="POSTGRES_SERVER")
    POSTGRES_USER: str = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="postgres", env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(default="downloader", env="POSTGRES_DB")
    POSTGRES_PORT: str = Field(default="5432", env="POSTGRES_PORT")
    DATABASE_URL: str | None = None

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # RabbitMQ / Celery
    CELERY_BROKER_URL: str = Field(default="amqp://guest:guest@localhost:5672//", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1", env="CELERY_RESULT_BACKEND")

    # Storage & Temp Settings
    DOWNLOAD_DIR: str = Field(
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "downloads"),
        env="DOWNLOAD_DIR"
    )
    TEMP_FILE_LIFETIME_SECONDS: int = 3600  # Clean up files older than 1 hour

    # Authentication / Cookie import (e.g. 'chrome', 'edge', 'firefox')
    COOKIES_FROM_BROWSER: str | None = Field(default=None, env="COOKIES_FROM_BROWSER")

    # Rate Limiting
    RATE_LIMIT_ANALYZE: str = "10/minute"
    RATE_LIMIT_DOWNLOAD: str = "5/minute"

    class Config:
        case_sensitive = True
        env_file = (os.path.join(backend_dir, ".env"), ".env")

    @property
    def backend_cors_origins(self) -> list[str]:
        value = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not value:
            return []
        if value.startswith("["):
            return [origin.rstrip("/") for origin in json.loads(value)]
        return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()

# Ensure download directory exists
os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)

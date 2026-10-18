import logging
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)

# Base configuration
celery_app = Celery(
    "media_downloader",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]
)

celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "beat_schedule": {
        "cleanup-every-hour": {
            "task": "app.tasks.cleanup_temp_files",
            "schedule": 3600.0,
        }
    }
}

# Connection health check to verify if RabbitMQ broker is running.
# If unavailable, run Celery in "eager mode" where tasks execute synchronously on the caller thread.
try:
    with celery_app.connection() as conn:
        conn.ensure_connection(max_retries=1, timeout=2)
    logger.info("Successfully connected to Celery message broker (RabbitMQ).")
except Exception as e:
    logger.warning(
        f"Could not connect to Celery Broker at {settings.CELERY_BROKER_URL} ({e}). "
        "Enabling Eager Mode (tasks will run synchronously on FastAPI server)."
    )
    celery_config["task_always_eager"] = True

celery_app.conf.update(celery_config)

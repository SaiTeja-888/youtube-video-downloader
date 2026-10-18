import redis
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis connection pool
try:
    pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client = redis.Redis(connection_pool=pool)
    redis_client.ping()
except Exception as e:
    logger.warning(f"Failed to initialize Redis pool: {e}")
    redis_client = None

def get_redis():
    return redis_client

# Progress cache keys helper
def get_progress_key(job_id: str) -> str:
    return f"progress:{job_id}"

# In-memory progress tracking fallback for local development without Redis
_memory_progress: dict[str, dict] = {}

def set_job_progress(job_id: str, progress: float, status: str = "downloading", error: str = None, file_path: str = None, file_size: int = None):
    global redis_client
    info = {
        "progress": float(progress),
        "status": status,
        "error": error,
        "file_path": file_path,
        "file_size": file_size
    }
    if not redis_client:
        _memory_progress[job_id] = info
        return
    try:
        mapping = {
            "progress": str(progress),
            "status": status,
            "error": error or "",
            "file_path": file_path or "",
            "file_size": str(file_size or 0)
        }
        redis_client.hset(get_progress_key(job_id), mapping=mapping)
        # Set TTL for progress info to 1 day
        redis_client.expire(get_progress_key(job_id), 86400)
    except Exception as e:
        logger.error(f"Redis write error in set_job_progress: {e}")
        redis_client = None
        _memory_progress[job_id] = info

def get_job_progress(job_id: str) -> dict | None:
    global redis_client
    if not redis_client:
        return _memory_progress.get(job_id)
    try:
        data = redis_client.hgetall(get_progress_key(job_id))
        if not data:
            return _memory_progress.get(job_id)
        return {
            "progress": float(data.get("progress", 0.0)),
            "status": data.get("status", "pending"),
            "error": data.get("error") if data.get("error") else None,
            "file_path": data.get("file_path") if data.get("file_path") else None,
            "file_size": int(data.get("file_size")) if data.get("file_size") and data.get("file_size") != "0" else None
        }
    except Exception as e:
        logger.error(f"Redis read error in get_job_progress: {e}")
        redis_client = None
        return _memory_progress.get(job_id)

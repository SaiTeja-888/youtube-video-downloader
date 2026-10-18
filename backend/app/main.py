import os
import sys

# Ensure backend directory is in PATH so that local ffmpeg.exe is accessible
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = backend_dir + os.pathsep + os.environ.get("PATH", "")

import uuid
import logging
import traceback
from datetime import datetime, date, timedelta
from urllib.parse import quote
from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base, get_db
from app.redis_client import redis_client, get_job_progress
from app.models import DownloadJob, SystemStat
from app.schemas import AnalyzeRequest, DownloadRequest, JobStatusResponse, HealthResponse, SystemStatsResponse, PlatformStat
from app.providers.manager import provider_manager
from app.tasks import download_media_task
from app.url_utils import normalize_media_url
from app.celery_app import celery_app

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

# Setup logging with UTF-8 encoding for unicode and emoji support
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Setup rate limiting
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.PROJECT_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves downloads directory
app.mount("/api/files", StaticFiles(directory=settings.DOWNLOAD_DIR), name="files")

@app.get("/api/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    postgres_status = "unhealthy"
    redis_status = "unhealthy"
    rabbitmq_status = "healthy"  # Mocked as celery connection handles it, let's verify Celery ping if needed

    # Test Postgres
    try:
        db.execute(text("SELECT 1"))
        postgres_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    # Test Redis
    try:
        if redis_client and redis_client.ping():
            redis_status = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    overall_status = "healthy" if (postgres_status == "healthy" and redis_status == "healthy") else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        postgres=postgres_status,
        redis=redis_status,
        rabbitmq=rabbitmq_status
    )

@app.post("/api/analyze")
@limiter.limit(settings.RATE_LIMIT_ANALYZE)
def analyze_url(request: Request, payload: AnalyzeRequest):
    try:
        url = normalize_media_url(payload.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Check Redis cache first to avoid redundant extraction hits
    cache_key = f"analyze_cache:{url}"
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached analysis for {url}")
                # We return standard JSON parsed data
                import json
                return JSONResponse(content=json.loads(cached_data))
        except Exception as e:
            logger.error(f"Redis cache read error: {e}")

    # Process analyzer
    try:
        provider = provider_manager.get_provider_for_url(url)
        metadata = provider.analyze(url)

        if metadata is None:
            raise ValueError("Extraction returned no data. The video may be unavailable, age-restricted, or region-locked.")
        
        # Save to Cache for 10 minutes (600s)
        response_data = metadata.model_dump()
        if redis_client:
            try:
                import json
                redis_client.setex(cache_key, 600, json.dumps(response_data))
            except Exception as e:
                logger.error(f"Redis cache write error: {e}")

        return response_data
    except Exception as e:
        logger.error(f"Error analyzing URL {url}: {e}")
        logger.debug(f"Traceback for {url}: {traceback.format_exc()}")
        err_msg = str(e)
        err_msg_lower = err_msg.lower()
        if "could not copy chrome cookie database" in err_msg_lower:
            detail = "YouTube bot protection active. Your Chrome cookie file is currently locked by the browser. Please close Chrome and try again, or configure Edge cookies in your environment (COOKIES_FROM_BROWSER=edge)."
        elif "sign in to confirm" in err_msg_lower or "not a bot" in err_msg_lower or "login required" in err_msg_lower:
            detail = "The platform blocked this request or requires login. For YouTube or Instagram private/login-gated media, configure browser cookies in your environment (e.g., COOKIES_FROM_BROWSER=chrome)."
        elif "drm protected" in err_msg_lower:
            detail = "This media file is DRM protected (Digital Rights Management) and cannot be legally extracted."
        elif "nonetype" in err_msg_lower or "no data" in err_msg_lower:
            detail = "Failed to extract video information. The video may be unavailable, age-restricted, members-only, or region-locked. Please try again."
        else:
            detail = f"Error parsing link: {err_msg}"
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )

@app.post("/api/download")
@limiter.limit(settings.RATE_LIMIT_DOWNLOAD)
def start_download(request: Request, payload: DownloadRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        url = normalize_media_url(payload.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    format_id = payload.format_id.strip()
    
    if not format_id:
        raise HTTPException(status_code=400, detail="A format must be selected.")

    # Create job UUID
    job_id = str(uuid.uuid4())
    logger.info(f"Creating job {job_id} for URL {url} with format {format_id}")

    try:
        # Pre-analyze or fetch metadata if cached to populate db
        provider = provider_manager.get_provider_for_url(url)
        platform = provider.detect_platform(url)
        title = "Extracting..."
        thumbnail = None
        duration = None

        cache_key = f"analyze_cache:{url}"
        if redis_client:
            try:
                import json
                cached = redis_client.get(cache_key)
                if cached:
                    meta = json.loads(cached)
                    title = meta.get("title", "Download")
                    thumbnail = meta.get("thumbnail")
                    duration = meta.get("duration")
            except Exception as re_err:
                logger.error(f"Redis lookup warning in start_download: {re_err}")

        # Save to Postgres
        db_job = DownloadJob(
            id=job_id,
            url=url,
            title=title,
            duration=duration,
            thumbnail=thumbnail,
            platform=platform,
            format_id=format_id,
            status="pending",
            progress=0.0
        )
        db.add(db_job)
        db.commit()

        # Trigger background Celery Task (or fallback to BackgroundTasks in eager/local mode)
        if celery_app.conf.task_always_eager:
            background_tasks.add_task(download_media_task, job_id, url, format_id)
        else:
            download_media_task.delay(job_id, url, format_id)

        return {"job_id": job_id}

    except Exception as e:
        logger.error(f"Failed to start download job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not initiate download job: {str(e)}"
        )

@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str, db: Session = Depends(get_db)):
    # Check redis first
    progress_info = get_job_progress(job_id)
    
    # Retrieve job from DB
    job = db.query(DownloadJob).filter(DownloadJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    res = JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error=job.error_message,
        title=job.title,
        thumbnail=job.thumbnail,
        platform=job.platform,
        file_size=job.file_size
    )

    # Sync Redis real-time status if present
    if progress_info:
        res.status = progress_info["status"]
        res.progress = progress_info["progress"]
        res.error = progress_info["error"]

    if res.status == "completed" and job.file_path:
        filename = os.path.basename(job.file_path)
        # Use the forced-download endpoint instead of static files (prevents browser playback)
        res.file_url = f"/api/download-file/{job.id}"

    return res

@app.get("/api/download-file/{job_id}")
def download_file(job_id: str, db: Session = Depends(get_db)):
    """Serve a completed download file with Content-Disposition: attachment to force browser download."""
    job = db.query(DownloadJob).filter(DownloadJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed" or not job.file_path:
        raise HTTPException(status_code=400, detail="File is not ready for download.")
    if not os.path.exists(job.file_path):
        raise HTTPException(status_code=404, detail="File no longer exists on server.")
    
    filename = os.path.basename(job.file_path)
    safe_filename = quote(filename)
    fallback_filename = filename.encode('ascii', errors='ignore').decode('ascii').replace('"', '\\"')
    if not fallback_filename:
        fallback_filename = "download"

    return FileResponse(
        path=job.file_path,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{fallback_filename}"; filename*=utf-8\'\'{safe_filename}',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        }
    )

@app.get("/api/admin/stats", response_model=SystemStatsResponse)
def get_admin_stats(db: Session = Depends(get_db)):
    # Totals
    total_dl = db.query(func.sum(SystemStat.total_downloads)).scalar() or 0
    success_dl = db.query(func.sum(SystemStat.successful_downloads)).scalar() or 0
    fail_dl = db.query(func.sum(SystemStat.failed_downloads)).scalar() or 0

    # Daily Stats (last 7 days)
    last_week = date.today() - timedelta(days=7)
    daily_query = db.query(SystemStat).filter(SystemStat.date >= last_week).order_by(SystemStat.date.asc()).all()
    
    daily_stats = []
    for day in daily_query:
        daily_stats.append({
            "date": day.date.isoformat(),
            "total": day.total_downloads,
            "success": day.successful_downloads,
            "failed": day.failed_downloads
        })

    # Platform Ratios
    # Merge platforms dictionary keys
    all_stats = db.query(SystemStat.platforms_count).all()
    platforms_merged = {}
    for row in all_stats:
        row_dict = row[0] or {}
        for plat, count in row_dict.items():
            platforms_merged[plat] = platforms_merged.get(plat, 0) + count

    platform_ratios = [PlatformStat(platform=p, count=c) for p, c in platforms_merged.items()]
    
    # Get current health status
    health = health_check(db)

    return SystemStatsResponse(
        total_downloads=total_dl,
        successful_downloads=success_dl,
        failed_downloads=fail_dl,
        daily_stats=daily_stats,
        platform_ratios=platform_ratios,
        health=health
    )

@app.get("/api/admin/logs")
def get_admin_logs():
    if not os.path.exists(log_file):
        return {"logs": "Log file not found."}
    try:
        with open(log_file, "r") as f:
            # Read last 200 lines
            lines = f.readlines()
            recent_logs = "".join(lines[-200:])
        return {"logs": recent_logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")

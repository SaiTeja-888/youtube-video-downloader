import os
import time
import logging
from datetime import datetime, timedelta
from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.redis_client import set_job_progress
from app.models import DownloadJob, SystemStat
from app.providers.manager import provider_manager

logger = logging.getLogger(__name__)

def update_db_job_status(job_id: str, status: str, progress: float = 0.0, file_path: str = None, file_size: int = None, error_message: str = None):
    try:
        with SessionLocal() as db:
            job = db.query(DownloadJob).filter(DownloadJob.id == job_id).first()
            if job:
                job.status = status
                job.progress = progress
                if file_path:
                    job.file_path = file_path
                if file_size:
                    job.file_size = file_size
                if error_message:
                    job.error_message = error_message
                if status in ["completed", "failed"]:
                    job.completed_at = datetime.utcnow()
                db.commit()
    except Exception as e:
        logger.warning(f"Could not update DB job status for {job_id}: {e}")

def increment_system_stats(platform: str, success: bool):
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            stat = db.query(SystemStat).filter(SystemStat.date == today).first()
            if not stat:
                stat = SystemStat(date=today)
                db.add(stat)
                db.commit()
                db.refresh(stat)

            stat.total_downloads += 1
            if success:
                stat.successful_downloads += 1
            else:
                stat.failed_downloads += 1

            # Safe update platform count
            counts = dict(stat.platforms_count or {})
            counts[platform] = counts.get(platform, 0) + 1
            stat.platforms_count = counts

            db.commit()
    except Exception as e:
        logger.warning(f"Could not increment system stats: {e}")

@celery_app.task(name="app.tasks.download_media")
def download_media_task(job_id: str, url: str, format_id: str):
    logger.info(f"Starting Celery task download_media for job_id={job_id}, url={url}, format={format_id}")
    
    # Initialize redis state
    set_job_progress(job_id, 0.0, "downloading")
    update_db_job_status(job_id, "downloading", 0.0)

    provider = provider_manager.get_provider_for_url(url)
    platform = provider.detect_platform(url)

    # Simple callback helper that reduces write load if progress doesn't change much
    last_reported = [0.0]
    last_db_update = [0.0]
    
    def progress_callback(progress_percent: float):
        import time as _time
        progress_percent = round(progress_percent, 1)
        now = _time.time()
        # Update Redis frequently (every 0.5% change) for responsive UI
        if progress_percent - last_reported[0] >= 0.5 or progress_percent == 100.0:
            last_reported[0] = progress_percent
            set_job_progress(job_id, progress_percent, "downloading")
        # Throttle DB writes to at most once per 3 seconds to reduce load
        if now - last_db_update[0] >= 3.0 or progress_percent == 100.0:
            last_db_update[0] = now
            update_db_job_status(job_id, "downloading", progress_percent)

    try:
        # Perform extraction download
        output_dir = settings.DOWNLOAD_DIR
        os.makedirs(output_dir, exist_ok=True)

        downloaded_file = provider.download(url, format_id, output_dir, progress_callback)
        
        if not os.path.exists(downloaded_file):
            raise FileNotFoundError(f"Media file failed to save or was not found: {downloaded_file}")

        file_size = os.path.getsize(downloaded_file)
        
        # Complete tasks in both Redis and DB
        set_job_progress(job_id, 100.0, "completed", file_path=downloaded_file, file_size=file_size)
        update_db_job_status(job_id, "completed", 100.0, file_path=downloaded_file, file_size=file_size)
        increment_system_stats(platform, success=True)
        
        logger.info(f"Task completed successfully: job_id={job_id}, file={downloaded_file}")
        return {"status": "completed", "file_path": downloaded_file, "file_size": file_size}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task failed: job_id={job_id}, error={error_msg}")
        
        set_job_progress(job_id, last_reported[0], "failed", error=error_msg)
        update_db_job_status(job_id, "failed", last_reported[0], error_message=error_msg)
        increment_system_stats(platform, success=False)
        
        return {"status": "failed", "error": error_msg}

@celery_app.task(name="app.tasks.cleanup_temp_files")
def cleanup_temp_files():
    logger.info("Starting Celery beat task: cleanup_temp_files")
    download_dir = settings.DOWNLOAD_DIR
    if not os.path.exists(download_dir):
        logger.info(f"Directory {download_dir} does not exist, skipping.")
        return

    now = time.time()
    deleted_count = 0
    
    for filename in os.listdir(download_dir):
        file_path = os.path.join(download_dir, filename)
        if os.path.isfile(file_path):
            file_mtime = os.path.getmtime(file_path)
            # If the file is older than the configured lifetime (1 hour)
            if now - file_mtime > settings.TEMP_FILE_LIFETIME_SECONDS:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Cleaned up expired media file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")

    logger.info(f"Cleanup finished. Deleted {deleted_count} file(s).")
    return {"deleted_files": deleted_count}

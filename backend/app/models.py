import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, BigInteger, Date
from app.database import Base

class DownloadJob(Base):
    __tablename__ = "download_jobs"

    id = Column(String, primary_key=True, index=True)  # Standard UUID string or task ID
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    thumbnail = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    format_id = Column(String, nullable=True)
    format_note = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False)  # pending, downloading, completed, failed
    progress = Column(Float, default=0.0, nullable=False)
    file_path = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

class SystemStat(Base):
    __tablename__ = "system_stats"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False, default=datetime.date.today)
    total_downloads = Column(Integer, default=0, nullable=False)
    successful_downloads = Column(Integer, default=0, nullable=False)
    failed_downloads = Column(Integer, default=0, nullable=False)
    platforms_count = Column(JSON, default=dict, nullable=False)  # e.g., {"youtube": 15, "instagram": 3}

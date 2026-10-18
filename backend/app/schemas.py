from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.providers.base import MediaFormat

class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="The media URL to analyze")

class DownloadRequest(BaseModel):
    url: str = Field(..., description="The media URL to download")
    format_id: str = Field(..., description="The format ID returned during analysis")

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    platform: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    postgres: str
    redis: str
    rabbitmq: str

class PlatformStat(BaseModel):
    platform: str
    count: int

class SystemStatsResponse(BaseModel):
    total_downloads: int
    successful_downloads: int
    failed_downloads: int
    daily_stats: List[dict]
    platform_ratios: List[PlatformStat]
    health: HealthResponse

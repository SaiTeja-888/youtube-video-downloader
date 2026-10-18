from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import List, Optional

class MediaFormat(BaseModel):
    format_id: str
    resolution: Optional[str] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    filesize: Optional[int] = None  # in bytes
    bitrate: Optional[float] = None  # in kbps
    container: str
    media_type: str  # "audio", "video", "muxed" (video+audio)
    url: Optional[str] = None  # Direct download URL if accessible

class MediaMetadata(BaseModel):
    url: str
    title: str
    duration: Optional[int] = None  # in seconds
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    views: Optional[int] = None
    upload_date: Optional[str] = None  # YYYYMMDD
    description: Optional[str] = None
    platform: str
    formats: List[MediaFormat] = Field(default_factory=list)

class BaseProvider(ABC):
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this provider supports the given URL."""
        pass

    @abstractmethod
    def analyze(self, url: str) -> MediaMetadata:
        """Extract metadata and available formats for the given URL."""
        pass

    @abstractmethod
    def download(self, url: str, format_id: str, output_path: str, progress_callback) -> str:
        """
        Download a specific format of the media to the output_path.
        progress_callback should accept a float (0.0 to 100.0).
        Returns the absolute path to the downloaded file.
        """
        pass

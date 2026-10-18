import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.providers.manager import provider_manager
from app.providers.ytdlp_provider import YtdlpProvider
from app.url_utils import normalize_media_url

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "postgres" in data
    assert "redis" in data

def test_provider_manager_routing():
    # YouTube URL
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    provider = provider_manager.get_provider_for_url(youtube_url)
    assert isinstance(provider, YtdlpProvider)
    assert provider.detect_platform(youtube_url) == "youtube"

    # Instagram URL
    instagram_url = "https://www.instagram.com/reel/CxYQe0orabc/"
    provider = provider_manager.get_provider_for_url(instagram_url)
    assert isinstance(provider, YtdlpProvider)
    assert provider.detect_platform(instagram_url) == "instagram"

    # Removed named support for Vimeo/TikTok; they now fall through as generic URLs.
    assert provider.detect_platform("https://vimeo.com/224392349") == "generic"
    assert provider.detect_platform("https://www.tiktok.com/@user/video/1234567890") == "generic"

    # Mobile YouTube URLs and links without a scheme should still be accepted.
    mobile_youtube_url = "m.youtube.com/watch?v=dQw4w9WgXcQ"
    provider = provider_manager.get_provider_for_url(mobile_youtube_url)
    assert isinstance(provider, YtdlpProvider)
    assert provider.detect_platform(mobile_youtube_url) == "youtube"

def test_normalize_media_url():
    assert normalize_media_url("youtu.be/dQw4w9WgXcQ#fragment") == "https://youtu.be/dQw4w9WgXcQ"

def test_invalid_analyze_payload():
    # Test blank payload
    response = client.post("/api/analyze", json={"url": ""})
    assert response.status_code == 400

    # Test missing payload fields
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422

def test_invalid_download_payload():
    # Test blank payload
    response = client.post("/api/download", json={"url": "", "format_id": ""})
    assert response.status_code == 400

def test_direct_link_detection():
    # Test that a direct link to an MP4 is detected as direct
    url = "https://www.w3schools.com/html/mov_bbb.mp4"
    provider = provider_manager.get_provider_for_url(url)
    assert isinstance(provider, YtdlpProvider)
    
    meta = provider.analyze(url)
    assert meta.platform == "generic"
    assert len(meta.formats) == 1
    assert meta.formats[0].format_id == "direct"
    assert meta.formats[0].container == "mp4"
    assert meta.formats[0].media_type == "video"

def test_direct_image_link_detection():
    url = "https://cdn.example.com/photos/sample-image.jpg"
    provider = provider_manager.get_provider_for_url(url)
    assert isinstance(provider, YtdlpProvider)

    meta = provider.analyze(url)
    assert meta.platform == "generic"
    assert len(meta.formats) == 1
    assert meta.formats[0].format_id == "direct"
    assert meta.formats[0].container == "jpg"
    assert meta.formats[0].media_type == "image"

def test_download_file_unicode_header(tmp_path):
    from app.database import SessionLocal
    from app.models import DownloadJob
    import uuid
    
    # Create a temp file on disk
    test_file = tmp_path / "test_file_：_｜_unicode.mp4"
    test_file.write_text("dummy content")
    
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        job = DownloadJob(
            id=job_id,
            url="https://example.com/unicode",
            title="Unicode Video",
            status="completed",
            progress=100.0,
            file_path=str(test_file)
        )
        db.add(job)
        db.commit()
        
        # Request file via client
        response = client.get(f"/api/download-file/{job_id}")
        assert response.status_code == 200
        
        cd_header = response.headers.get("content-disposition")
        assert cd_header is not None
        assert "filename*=" in cd_header
        assert "utf-8" in cd_header
        
    finally:
        db.query(DownloadJob).filter(DownloadJob.id == job_id).delete()
        db.commit()
        db.close()

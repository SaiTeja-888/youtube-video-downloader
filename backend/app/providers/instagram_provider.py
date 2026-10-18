import os
import re
import time
import shutil
import logging
import subprocess
from urllib.parse import urlparse
import requests

from app.config import settings
from app.providers.base import BaseProvider, MediaFormat, MediaMetadata
from app.url_utils import hostname_for_url, normalize_media_url

logger = logging.getLogger(__name__)

class InstagramProvider(BaseProvider):
    """
    Dedicated high-reliability provider for Instagram Reels, Posts, and Carousels.
    Uses multi-stage extraction:
    1. Embed contextJSON & Polaris GraphQL extraction (no login required)
    2. Fallback to parth_dl engine
    3. Fallback to yt-dlp with session cookies / browser integration
    """

    def can_handle(self, url: str) -> bool:
        try:
            host = hostname_for_url(url)
            return host in {"instagram.com", "instagr.am"} or host.endswith(".instagram.com") or host.endswith(".instagr.am")
        except Exception:
            return False

    def detect_platform(self, url: str) -> str:
        return "instagram"

    def _get_ffmpeg_path(self) -> str | None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_ffmpeg = os.path.join(backend_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
        which_ffmpeg = shutil.which("ffmpeg")
        if which_ffmpeg:
            return which_ffmpeg
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            import glob
            matches = glob.glob(os.path.join(localappdata, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "ffmpeg.exe"), recursive=True)
            if matches:
                return matches[0]
        return None

    def _extract_shortcode(self, url: str) -> str | None:
        try:
            from parth_dl.utils import extract_instagram_id
            return extract_instagram_id(url)
        except Exception:
            m = re.search(r'/(?:reel|reels|p|share/reel)/([A-Za-z0-9_-]+)', url)
            return m.group(1) if m else None

    def analyze(self, url: str) -> MediaMetadata:
        url = normalize_media_url(url)
        shortcode = self._extract_shortcode(url)

        # 1. Attempt extraction via parth_dl
        try:
            import parth_dl
            logger.info(f"[InstagramProvider] Analyzing Instagram URL: {url} (shortcode: {shortcode})")
            info = parth_dl.get_info(url)
            if info and info.get("entries"):
                return self._build_metadata_from_parth(url, info, shortcode)
        except Exception as e:
            logger.warning(f"[InstagramProvider] parth_dl extraction failed ({e}), falling back to yt-dlp...")

        # 2. Fallback to YtdlpProvider
        from app.providers.ytdlp_provider import YtdlpProvider
        ydl_prov = YtdlpProvider()
        try:
            return ydl_prov.analyze(url)
        except Exception as yt_err:
            logger.error(f"[InstagramProvider] All Instagram extraction methods failed: {yt_err}")
            raise ValueError(
                "Could not access Instagram reel. The post may be private, restricted, or deleted. "
                "Only public Instagram reels and posts can be downloaded."
            )

    def _build_metadata_from_parth(self, url: str, info: dict, shortcode: str | None) -> MediaMetadata:
        title = info.get("title") or (f"Instagram Reel by @{info.get('uploader')}" if info.get("uploader") else "Instagram Reel")
        title = re.sub(r'[\r\n]+', ' ', title).strip()[:100] or "Instagram Reel"
        duration = int(info.get("duration")) if info.get("duration") is not None else None
        uploader = info.get("uploader") or "Instagram User"
        thumbnail = info.get("thumbnail")
        entries = info.get("entries", [])

        formats: list[MediaFormat] = []
        has_video = False

        for idx, entry in enumerate(entries):
            kind = entry.get("kind", "video")
            entry_formats = entry.get("formats", [])
            for f_idx, fmt in enumerate(entry_formats):
                fmt_url = fmt.get("url")
                w = fmt.get("width")
                h = fmt.get("height")
                res = f"{w}p" if w and not h else (f"{h}p" if h and not w else (f"{w}x{h}" if w and h else "Original (HD)"))

                if kind == "video":
                    has_video = True
                    fid = "best" if idx == 0 and f_idx == 0 else f"video_{idx}_{f_idx}"
                    formats.append(MediaFormat(
                        format_id=fid,
                        resolution=f"Original Reel ({res})" if idx == 0 else f"Reel Video {idx+1} ({res})",
                        fps=None,
                        codec="h264/aac",
                        container="mp4",
                        media_type="muxed",
                        url=fmt_url
                    ))
                elif kind == "image":
                    fid = f"image_{idx}_{f_idx}"
                    formats.append(MediaFormat(
                        format_id=fid,
                        resolution=f"Original Photo ({res})",
                        fps=None,
                        codec="jpeg",
                        container="jpg",
                        media_type="image",
                        url=fmt_url
                    ))

        # If at least one video exists, provide an Audio-only extraction format
        if has_video:
            formats.append(MediaFormat(
                format_id="audio",
                resolution="Audio Track Only",
                fps=None,
                codec="aac",
                container="m4a",
                media_type="audio"
            ))

        if not formats:
            raise ValueError("No downloadable media formats found for this Instagram post.")

        return MediaMetadata(
            url=url,
            title=title,
            duration=duration,
            thumbnail=thumbnail,
            uploader=f"@{uploader}" if not uploader.startswith("@") else uploader,
            views=None,
            upload_date=None,
            description=info.get("title") or "",
            platform="instagram",
            formats=formats
        )

    def download(self, url: str, format_id: str, output_path: str, progress_callback) -> str:
        url = normalize_media_url(url)
        format_id = (format_id or "best").strip()
        os.makedirs(output_path, exist_ok=True)
        shortcode = self._extract_shortcode(url) or "reel"

        # Try parth-dl first
        try:
            return self._download_via_parth(url, format_id, output_path, shortcode, progress_callback)
        except Exception as e:
            logger.warning(f"[InstagramProvider] Direct parth-dl download failed ({e}), falling back to yt-dlp...")

        # Fallback to YtdlpProvider
        from app.providers.ytdlp_provider import YtdlpProvider
        ydl_prov = YtdlpProvider()
        return ydl_prov.download(url, "best", output_path, progress_callback)

    def _download_via_parth(self, url: str, format_id: str, output_path: str, shortcode: str, progress_callback) -> str:
        import parth_dl
        info = parth_dl.get_info(url)
        if not info or not info.get("entries"):
            raise ValueError("Could not extract media info from Instagram URL.")

        raw_title = info.get("title") or f"instagram_{shortcode}"
        safe_title = re.sub(r'[^\w\-]', '_', raw_title)[:60]
        if not safe_title.strip():
            safe_title = f"instagram_{shortcode}"

        epoch = int(time.time())

        # Audio only request
        if format_id == "audio":
            # 1. Download video first
            video_url = self._find_stream_url(info, "best")
            if not video_url:
                raise ValueError("No video stream found to extract audio from.")

            temp_video = os.path.join(output_path, f"temp_{shortcode}_{epoch}.mp4")
            try:
                self._stream_download(video_url, temp_video, lambda p: progress_callback(p * 0.85))
                # 2. Extract audio via ffmpeg
                audio_output = os.path.join(output_path, f"{safe_title}_{shortcode}_{epoch}.m4a")
                ffmpeg_bin = self._get_ffmpeg_path() or "ffmpeg"
                cmd = [
                    ffmpeg_bin, "-y", "-i", temp_video,
                    "-vn", "-c:a", "aac", "-b:a", "192k",
                    audio_output
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                progress_callback(100.0)
                return audio_output
            finally:
                if os.path.exists(temp_video):
                    try:
                        os.remove(temp_video)
                    except Exception:
                        pass

        # Video or Image stream
        stream_url = self._find_stream_url(info, format_id)
        if stream_url:
            ext = "jpg" if "image" in format_id else "mp4"
            dest_file = os.path.join(output_path, f"{safe_title}_{shortcode}_{epoch}.{ext}")
            return self._stream_download(stream_url, dest_file, progress_callback)

        # Fallback to parth_dl.download directly
        progress_callback(10.0)
        res = parth_dl.download(url, output_path=output_path)
        progress_callback(100.0)
        if isinstance(res, str) and os.path.exists(res):
            return res
        # Check files created in output_path with shortcode
        for f in os.listdir(output_path):
            if shortcode in f:
                fpath = os.path.join(output_path, f)
                if os.path.isfile(fpath):
                    return fpath
        raise FileNotFoundError("Could not find downloaded file on disk.")

    def _find_stream_url(self, info: dict, format_id: str) -> str | None:
        entries = info.get("entries", [])
        if not entries:
            return None

        # Best / default
        if format_id in {"best", "original", ""}:
            for entry in entries:
                if entry.get("kind") == "video":
                    fmts = entry.get("formats", [])
                    if fmts and fmts[0].get("url"):
                        return fmts[0]["url"]
            # Fallback to image if no video
            for entry in entries:
                fmts = entry.get("formats", [])
                if fmts and fmts[0].get("url"):
                    return fmts[0]["url"]

        # Search by specific format_id
        for entry in entries:
            for fmt in entry.get("formats", []):
                if fmt.get("format_id") == format_id:
                    return fmt.get("url")

        # Fallback to first available url
        for entry in entries:
            for fmt in entry.get("formats", []):
                if fmt.get("url"):
                    return fmt.get("url")
        return None

    def _stream_download(self, url: str, dest_file: str, progress_callback) -> str:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': '*/*',
            'Referer': 'https://www.instagram.com/',
        }
        proxies = None
        proxy = os.environ.get("YTDL_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if proxy and proxy.strip():
            proxies = {"http": proxy.strip(), "https": proxy.strip()}

        with requests.get(url, headers=headers, stream=True, timeout=60, proxies=proxies) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(dest_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = min((downloaded / total) * 100, 99.0)
                            progress_callback(pct)
        progress_callback(100.0)
        return dest_file

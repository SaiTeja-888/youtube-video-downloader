import os
import re
import shutil
import time
import requests
from urllib.parse import urlparse
import yt_dlp
from app.config import settings
from app.providers.base import BaseProvider, MediaFormat, MediaMetadata
from app.url_utils import hostname_for_url, normalize_media_url

# Public Invidious instances (open-source YouTube frontends with their own IPs)
# If one is down the next is tried automatically — no config needed
_INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.tiekoetter.com",
    "https://invidious.f5.si",
    "https://yt.chocolatemoo53.com",
    "https://yewtu.be",
    "https://invidious.nerdvpn.de",
    "https://invidious.privacydev.net",
    "https://invidious.io",
]

# Public Piped API instances (another open-source YouTube proxy)
_PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.tokhmi.xyz",
    "https://watchapi.whatever.social",
    "https://api.piped.projectsegfau.lt",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.in.projectsegfau.lt",
]

class YtdlpProvider(BaseProvider):
    def can_handle(self, url: str) -> bool:
        try:
            normalize_media_url(url)
            return True
        except ValueError:
            return False

    def detect_platform(self, url: str) -> str:
        host = hostname_for_url(url)
        if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
            return "youtube"
        elif host in {"instagram.com", "instagr.am"} or host.endswith(".instagram.com") or host.endswith(".instagr.am"):
            return "instagram"
        elif host in {"x.com", "twitter.com"} or host.endswith(".x.com") or host.endswith(".twitter.com"):
            return "twitter"
        return "generic"

    def _is_direct_media_url(self, url: str) -> tuple[bool, str, str]:
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            ext_to_mime = {
                '.mp4': ('video', 'mp4'),
                '.mkv': ('video', 'mkv'),
                '.webm': ('video', 'webm'),
                '.avi': ('video', 'avi'),
                '.mov': ('video', 'mov'),
                '.mp3': ('audio', 'mp3'),
                '.m4a': ('audio', 'm4a'),
                '.wav': ('audio', 'wav'),
                '.aac': ('audio', 'aac'),
                '.flac': ('audio', 'flac'),
                '.jpg': ('image', 'jpg'),
                '.jpeg': ('image', 'jpeg'),
                '.png': ('image', 'png'),
                '.webp': ('image', 'webp'),
                '.heic': ('image', 'heic'),
            }
            for ext, (mtype, container) in ext_to_mime.items():
                if path.endswith(ext):
                    return True, mtype, container

            # HTTP HEAD check with 2-second timeout
            r = requests.head(url, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True, timeout=2)
            content_type = r.headers.get('Content-Type', '').lower()
            if content_type.startswith('video/'):
                container = content_type.split('/')[-1].split(';')[0].strip() or 'mp4'
                return True, 'video', container
            elif content_type.startswith('audio/'):
                container = content_type.split('/')[-1].split(';')[0].strip() or 'mp3'
                return True, 'audio', container
            elif content_type.startswith('image/'):
                container = content_type.split('/')[-1].split(';')[0].strip() or 'jpg'
                return True, 'image', container
        except Exception:
            pass
        return False, '', ''

    def _normalize_cookie_content(self, text: str) -> str:
        if not text:
            return ""
        import base64
        # Handle base64 encoded cookies
        try:
            decoded = base64.b64decode(text.strip()).decode('utf-8')
            if "youtube.com" in decoded or "google.com" in decoded or "NETSCAPE" in decoded.upper():
                text = decoded
        except Exception:
            pass

        # Handle literal escaped newlines
        if "\\n" in text and "\n" not in text:
            text = text.replace("\\r\\n", "\n").replace("\\n", "\n")

        lines = text.splitlines()
        out = ["# Netscape HTTP Cookie File", "# Auto-normalized by YtdlpProvider"]
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 6)
            if len(parts) >= 7:
                domain, flag, path, secure, expiration, name, value = parts
                out.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")
            elif len(parts) == 6:
                domain, flag, path, secure, expiration, name = parts
                out.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t")
        return "\n".join(out) + "\n"

    def _cookies_file(self) -> str | None:
        import tempfile
        # 1. Check raw cookie text from environment variable (ideal for Render env vars)
        raw_cookies = os.environ.get("COOKIES_TEXT") or os.environ.get("YOUTUBE_COOKIES") or os.environ.get("COOKIES_BASE64")
        if raw_cookies and raw_cookies.strip():
            normalized = self._normalize_cookie_content(raw_cookies)
            auto_path = os.path.join(tempfile.gettempdir(), "postlink_auto_cookies.txt")
            try:
                with open(auto_path, "w", encoding="utf-8") as f:
                    f.write(normalized)
                return auto_path
            except Exception:
                pass

        # 2. Check explicit env path
        env_path = os.environ.get("COOKIE_FILE") or os.environ.get("COOKIES_FILE")
        if env_path and os.path.exists(env_path):
            return env_path

        # 3. Check Render Secret Files default mount path
        render_secret = "/etc/secrets/cookies.txt"
        if os.path.exists(render_secret):
            try:
                with open(render_secret, "r", encoding="utf-8") as f:
                    sec_content = f.read()
                normalized = self._normalize_cookie_content(sec_content)
                sec_path = os.path.join(tempfile.gettempdir(), "postlink_render_cookies.txt")
                with open(sec_path, "w", encoding="utf-8") as f:
                    f.write(normalized)
                return sec_path
            except Exception:
                return render_secret

        # 4. Check local backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_cookie = os.path.join(backend_dir, "cookies.txt")
        if os.path.exists(local_cookie):
            return local_cookie

        # 5. Check project root directory
        root_dir = os.path.dirname(backend_dir)
        root_cookie = os.path.join(root_dir, "cookies.txt")
        if os.path.exists(root_cookie):
            return root_cookie

        return None

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

    def _ffmpeg_available(self) -> bool:
        return self._get_ffmpeg_path() is not None

    def _is_server_environment(self) -> bool:
        """Detect if we're running in a headless server (Render, Vercel, Docker, etc.)."""
        # Common server environment indicators
        if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
            return True
        if os.environ.get("DYNO"):  # Heroku
            return True
        if os.environ.get("KUBERNETES_SERVICE_HOST"):
            return True
        # If no DISPLAY and no APPDATA (no desktop environment)
        if not os.environ.get("DISPLAY") and not os.environ.get("APPDATA"):
            return True
        return False

    def _get_browser_for_cookies(self) -> str | None:
        # Never try to extract browser cookies in a server environment — there's no browser
        if self._is_server_environment():
            return None
        if settings.COOKIES_FROM_BROWSER:
            return settings.COOKIES_FROM_BROWSER
        # Auto-detect available browsers on Windows/Linux/Mac (local dev only)
        appdata = os.environ.get("APPDATA", "")
        if appdata and os.path.exists(os.path.join(appdata, "Mozilla", "Firefox", "Profiles")):
            return "firefox"
        return None

    def _get_youtube_extractor_args(self, clients: list[str] | None = None) -> dict:
        """
        Build YouTube extractor_args using server-safe clients.
        tv_embedded / mweb / android_creator work on server IPs without cookies.
        Optionally inject PO_TOKEN + VISITOR_DATA env vars for extra access.
        """
        if clients is None:
            clients = ['tv_embedded', 'mweb', 'android_creator', 'android', 'ios']

        extractor_args: dict = {
            'youtube': {
                'player_client': clients,
            }
        }

        po_token = os.environ.get("PO_TOKEN", "").strip()
        visitor_data = os.environ.get("VISITOR_DATA", "").strip()
        if po_token:
            extractor_args['youtube']['po_token'] = [f'mweb+{po_token}', f'tv_embedded+{po_token}']
        if visitor_data:
            extractor_args['youtube']['visitor_data'] = visitor_data

        return extractor_args

    # All client combos to try, ordered from most-server-safe to least
    _YT_CLIENT_FALLBACK_CHAIN: list[list[str]] = [
        ['tv_embedded'],
        ['mweb'],
        ['tv_embedded', 'mweb'],
        ['android_creator'],
        ['android_creator', 'tv_embedded'],
        ['android'],
        ['android', 'tv_embedded'],
        ['ios'],
        ['tv'],
        ['android', 'ios', 'tv_embedded', 'mweb'],
    ]

    def _base_ydl_opts(self, platform: str = "") -> dict:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'extract_flat': False,
            'noplaylist': True,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Linux; Android 13; Pixel 7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.6099.230 Mobile Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }

        ffmpeg_bin = self._get_ffmpeg_path()
        if ffmpeg_bin:
            opts['ffmpeg_location'] = ffmpeg_bin

        if shutil.which("node"):
            opts['js_runtimes'] = {'node': {}}

        if platform == "youtube":
            opts['extractor_args'] = self._get_youtube_extractor_args()

        cookie_file = self._cookies_file()
        if cookie_file and os.path.exists(cookie_file):
            opts['cookiefile'] = cookie_file
        else:
            browser = self._get_browser_for_cookies()
            if browser:
                opts['cookiesfrombrowser'] = (browser,)

        proxy = os.environ.get("YTDL_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if proxy and proxy.strip():
            opts['proxy'] = proxy.strip()

        return opts

    def _try_youtube_with_all_clients(self, url: str, base_opts: dict, download: bool = False) -> dict | None:
        """
        Exhaustively try every known server-safe YouTube client combination.
        Returns the first successful info dict, or None if all fail.
        Stops immediately on definitive bot-block (avoids 20× log spam).
        """
        _BOT_BLOCK = ["sign in to confirm", "confirm you're not a bot", "not a bot"]
        for clients in self._YT_CLIENT_FALLBACK_CHAIN:
            for strip_cookies in [False, True]:
                try:
                    opts = dict(base_opts)
                    if strip_cookies:
                        opts.pop('cookiefile', None)
                        opts.pop('cookiesfrombrowser', None)
                    opts['extractor_args'] = self._get_youtube_extractor_args(clients=clients)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=download)
                        if info and (info.get('formats') or info.get('url')):
                            return info
                except Exception as e:
                    err = str(e).lower()
                    # YouTube is blocking ALL server IPs — stop immediately, go to Invidious
                    if any(k in err for k in _BOT_BLOCK):
                        return None
                    continue
        return None

    # ------------------------------------------------------------------ #
    #  Invidious / Piped fallback — bypasses YouTube's server-IP blocks   #
    # ------------------------------------------------------------------ #

    def _extract_youtube_video_id(self, url: str) -> str | None:
        """Extract the 11-char YouTube video ID from any YouTube URL format."""
        m = re.search(
            r'(?:v=|/embed/|/shorts/|/live/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            url
        )
        return m.group(1) if m else None

    def _try_invidious_analyze(self, url: str) -> 'MediaMetadata | None':
        """
        Fetch video metadata + direct CDN stream URLs from public Invidious instances.
        These instances have non-datacenter IPs that YouTube doesn't block.
        Works for ALL public YouTube videos with zero configuration.
        """
        import logging
        logger = logging.getLogger(__name__)

        video_id = self._extract_youtube_video_id(url)
        if not video_id:
            return None

        logger.info(f"[Invidious] Trying fallback for video_id={video_id}")

        for instance in _INVIDIOUS_INSTANCES:
            try:
                resp = requests.get(
                    f"{instance}/api/v1/videos/{video_id}",
                    timeout=12,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                if resp.status_code != 200:
                    logger.warning(f"[Invidious] {instance} returned HTTP {resp.status_code}")
                    continue
                data = resp.json()
                if 'error' in data or not data.get('title'):
                    continue

                formats: list[MediaFormat] = []
                seen: set[str] = set()

                # Combined streams — video+audio merged, ready to download
                for f in data.get('formatStreams', []):
                    itag = str(f.get('itag', ''))
                    fmt_url = f.get('url', '')
                    if not fmt_url or itag in seen:
                        continue
                    seen.add(itag)
                    formats.append(MediaFormat(
                        format_id=f"invidious_{itag}",
                        resolution=f.get('qualityLabel', f.get('quality', 'unknown')),
                        fps=f.get('fps'),
                        codec=f.get('encoding', 'unknown'),
                        container=f.get('container', 'mp4'),
                        media_type='muxed',
                        url=fmt_url,
                    ))

                # Adaptive streams — separate video or audio tracks
                for f in data.get('adaptiveFormats', []):
                    itag = str(f.get('itag', ''))
                    fmt_url = f.get('url', '')
                    if not fmt_url or itag in seen:
                        continue
                    seen.add(itag)
                    mime = f.get('type', '')
                    if mime.startswith('video/'):
                        media_type = 'video'
                        resolution = f.get('qualityLabel', 'unknown')
                    elif mime.startswith('audio/'):
                        media_type = 'audio'
                        resolution = 'Audio'
                    else:
                        continue
                    container = mime.split('/')[-1].split(';')[0].strip() or 'mp4'
                    formats.append(MediaFormat(
                        format_id=f"invidious_{itag}",
                        resolution=resolution,
                        fps=f.get('fps'),
                        codec=f.get('encoding', 'unknown'),
                        container=container,
                        media_type=media_type,
                        url=fmt_url,
                    ))

                if not formats:
                    continue

                # Best thumbnail
                thumbnail = None
                thumbs = data.get('videoThumbnails', [])
                for thumb in reversed(thumbs):
                    t = thumb.get('url', '')
                    if t:
                        thumbnail = t if t.startswith('http') else (
                            f"https:{t}" if t.startswith('//') else f"{instance}{t}"
                        )
                        break

                logger.info(f"[Invidious] SUCCESS via {instance} — {len(formats)} formats found")
                return MediaMetadata(
                    url=url,
                    title=data.get('title', 'Unknown Title'),
                    duration=data.get('lengthSeconds'),
                    thumbnail=thumbnail,
                    uploader=data.get('author', 'Unknown'),
                    views=data.get('viewCount'),
                    upload_date=str(data.get('published', '')),
                    description=(data.get('description') or '')[:500],
                    platform='youtube',
                    formats=formats,
                )
            except Exception as ex:
                logger.warning(f"[Invidious] {instance} error: {ex}")
                continue

        logger.warning(f"[Invidious] All instances failed for video_id={video_id}, trying Piped...")
        # Try Piped as final fallback
        return self._try_piped_analyze(url)

    def _try_piped_analyze(self, url: str) -> 'MediaMetadata | None':
        """
        Use Piped API (another open-source YouTube proxy) as a second fallback.
        """
        video_id = self._extract_youtube_video_id(url)
        if not video_id:
            return None

        for instance in _PIPED_INSTANCES:
            try:
                resp = requests.get(
                    f"{instance}/streams/{video_id}",
                    timeout=12,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if 'error' in data or not data.get('title'):
                    continue

                formats: list[MediaFormat] = []

                # Muxed / combined video+audio streams
                for f in data.get('videoStreams', []):
                    fmt_url = f.get('url', '')
                    quality = f.get('quality', 'unknown')
                    if not fmt_url or f.get('videoOnly', False):
                        continue
                    fid = f"piped_v_{re.sub(r'[^a-zA-Z0-9]', '_', quality)}"
                    formats.append(MediaFormat(
                        format_id=fid,
                        resolution=quality,
                        fps=f.get('fps'),
                        codec=f.get('codec', 'unknown'),
                        container='mp4',
                        media_type='muxed',
                        url=fmt_url,
                    ))

                # Audio-only streams
                for f in data.get('audioStreams', []):
                    fmt_url = f.get('url', '')
                    quality = f.get('quality', 'Audio')
                    if not fmt_url:
                        continue
                    fid = f"piped_a_{re.sub(r'[^a-zA-Z0-9]', '_', quality)}"
                    formats.append(MediaFormat(
                        format_id=fid,
                        resolution='Audio',
                        fps=None,
                        codec=f.get('codec', 'unknown'),
                        container='m4a',
                        media_type='audio',
                        url=fmt_url,
                    ))

                if not formats:
                    continue

                return MediaMetadata(
                    url=url,
                    title=data.get('title', 'Unknown Title'),
                    duration=data.get('duration'),
                    thumbnail=data.get('thumbnailUrl', ''),
                    uploader=data.get('uploader', 'Unknown'),
                    views=data.get('views'),
                    upload_date=None,
                    description=(data.get('description') or '')[:500],
                    platform='youtube',
                    formats=formats,
                )
            except Exception:
                continue

        return None

    def _download_from_direct_url(self, direct_url: str, output_path: str,
                                   filename_hint: str, progress_callback) -> str:
        """Stream-download from a direct URL (used for Invidious/Piped formats)."""
        safe_hint = re.sub(r'[^\w\-.]', '_', filename_hint)[:80]
        output_file = os.path.join(output_path, f"{safe_hint}_{int(time.time())}.mp4")
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Linux; Android 13; Pixel 7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.6099.230 Mobile Safari/537.36'
            ),
            'Referer': 'https://www.youtube.com/',
        }
        try:
            response = requests.get(direct_url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress_callback(min((downloaded / total_size) * 100, 99.0))
            progress_callback(100.0)
            return output_file
        except Exception:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass
            raise

    def analyze(self, url: str) -> MediaMetadata:
        url = normalize_media_url(url)
        platform = self.detect_platform(url)
        
        # Check direct link first to bypass slow extraction
        is_direct, mtype, ext = self._is_direct_media_url(url)
        if is_direct:
            title = os.path.basename(urlparse(url).path) or "Direct File"
            title = os.path.splitext(title)[0]
            title = title.replace('_', ' ').replace('-', ' ').title()
            
            formats = [
                MediaFormat(
                    format_id="direct",
                    resolution="Direct File Download",
                    fps=None,
                    codec="direct stream",
                    container=ext,
                    media_type=mtype,
                    url=url
                )
            ]
            return MediaMetadata(
                url=url,
                title=title,
                duration=None,
                thumbnail=None,
                uploader="Direct Link",
                views=None,
                upload_date=None,
                description=f"Directly download the source {mtype} file.",
                platform="generic",
                formats=formats
            )

        ydl_opts = self._base_ydl_opts(platform=platform)
        if platform == "instagram":
            ydl_opts['noplaylist'] = False
        info = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            err_lower = str(exc).lower()
            # For YouTube: try all yt-dlp clients first (fast-fails on bot block)
            if platform == "youtube":
                info = self._try_youtube_with_all_clients(url, ydl_opts, download=False)

            # If yt-dlp failed completely and this is YouTube, use Invidious/Piped
            if not info and platform == "youtube":
                invidious_result = self._try_invidious_analyze(url)
                if invidious_result:
                    return invidious_result  # ← Direct return, bypasses yt-dlp entirely

            if not info:
                raise exc

        if not info:
            # One more attempt via Invidious for YouTube before giving up
            if platform == "youtube":
                invidious_result = self._try_invidious_analyze(url)
                if invidious_result:
                    return invidious_result
            raise ValueError("Failed to extract metadata from URL.")

        if platform == "instagram":
            formats = [
                MediaFormat(
                    format_id="best",
                    resolution="Original Reel/Image",
                    fps=None,
                    codec="best available",
                    container="mp4/jpg",
                    media_type="muxed"
                )
            ]
        else:
            default_mp4_fmt = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
                if self._ffmpeg_available()
                else "best"
            )
            formats = [
                MediaFormat(
                    format_id=default_mp4_fmt,
                    resolution="Recommended MP4 (with audio)",
                    fps=None,
                    codec="best compatible",
                    container="mp4",
                    media_type="muxed"
                ),
                MediaFormat(
                    format_id="bestaudio[ext=m4a]/bestaudio/best",
                    resolution="Recommended Audio",
                    fps=None,
                    codec="best audio",
                    container="m4a",
                    media_type="audio"
                )
            ]
        seen_format_ids = {item.format_id for item in formats}

        # Extract formats
        raw_formats = info.get('formats', [])
        for f in raw_formats:
            # Filter out formatting options that aren't useful
            # For YouTube and Instagram reels we want to allow audio only or video formats.
            # Let's extract sizes, containers, codecs.
            ext = f.get('ext', '')
            format_id = f.get('format_id', '')
            if not ext or not format_id:
                continue

            resolution = None
            fps = f.get('fps')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            
            # Check media type
            if vcodec != 'none' and acodec != 'none':
                media_type = "muxed"
                resolution = f.get('resolution') or f"{f.get('width')}x{f.get('height')}"
            elif vcodec != 'none':
                media_type = "video"
                resolution = f.get('resolution') or f"{f.get('width')}x{f.get('height')}"
            elif acodec != 'none':
                media_type = "audio"
                resolution = "Audio"
            else:
                continue

            # For video-only formats, automatically request merging with bestaudio
            # so the downloaded video will have sound. yt-dlp handles this using ffmpeg.
            target_format_id = format_id
            if media_type == "video":
                target_format_id = f"{format_id}+bestaudio/best"

            if target_format_id in seen_format_ids:
                continue

            # Clean up resolution format e.g. "1920x1080" to "1080p"
            if resolution and "x" in resolution:
                parts = resolution.split("x")
                if len(parts) == 2 and parts[1].isdigit():
                    resolution = f"{parts[1]}p"
                else:
                    resolution = "Standard"

            codec = f"v:{vcodec}, a:{acodec}" if media_type == "muxed" else (vcodec if media_type == "video" else acodec)
            
            # Filter out standard non-user codecs
            if codec == "none" or not codec:
                codec = "unknown"

            # Estimated filesize
            filesize = f.get('filesize') or f.get('filesize_approx')

            seen_format_ids.add(target_format_id)
            formats.append(MediaFormat(
                format_id=target_format_id,
                resolution=resolution,
                fps=fps,
                codec=codec,
                filesize=filesize,
                bitrate=f.get('tbr'),
                container=ext,
                media_type=media_type,
                url=f.get('url')  # Might be direct download URL
            ))

        if not raw_formats and platform == "instagram":
            instagram_ext = (info.get('ext') or '').lower()
            instagram_url = info.get('url')
            if instagram_url and instagram_ext in {'jpg', 'jpeg', 'png', 'webp', 'heic', 'mp4'}:
                is_image = instagram_ext in {'jpg', 'jpeg', 'png', 'webp', 'heic'}
                if is_image:
                    formats = []
                formats.append(MediaFormat(
                    format_id="best",
                    resolution="Original Image" if is_image else "Original Video",
                    fps=None,
                    codec="image" if is_image else "best compatible",
                    filesize=info.get('filesize') or info.get('filesize_approx'),
                    bitrate=None,
                    container=instagram_ext,
                    media_type="image" if is_image else "muxed",
                    url=instagram_url
                ))

        if self._ffmpeg_available():
            formats.append(MediaFormat(
                format_id="bestvideo+bestaudio/best",
                resolution="Highest Quality (requires merge)",
                fps=60,
                codec="best",
                container="mp4",
                media_type="muxed"
            ))

        # Safely extract thumbnail
        thumbnail = info.get('thumbnail')
        if not thumbnail:
            thumbnails = info.get('thumbnails')
            if thumbnails and isinstance(thumbnails, list):
                for thumb in thumbnails:
                    if isinstance(thumb, dict) and thumb.get('url'):
                        thumbnail = thumb['url']
                        break

        return MediaMetadata(
            url=url,
            title=info.get('title') or 'Unknown Title',
            duration=info.get('duration'),
            thumbnail=thumbnail,
            uploader=info.get('uploader') or info.get('author') or 'Unknown Uploader',
            views=info.get('view_count'),
            upload_date=info.get('upload_date'),
            description=info.get('description'),
            platform=platform,
            formats=formats
        )


    def download(self, url: str, format_id: str, output_path: str, progress_callback) -> str:
        url = normalize_media_url(url)
        platform = self.detect_platform(url)
        format_id = (format_id or "").strip()
        if not format_id:
            raise ValueError("A format must be selected before downloading.")

        # Handle Invidious / Piped format IDs — re-fetch fresh CDN URL and stream directly
        if format_id.startswith("invidious_") or format_id.startswith("piped_"):
            # Re-fetch from Invidious/Piped to get a fresh (non-expired) stream URL
            meta = self._try_invidious_analyze(url)
            if meta:
                for fmt in meta.formats:
                    if fmt.format_id == format_id and fmt.url:
                        video_id = self._extract_youtube_video_id(url) or "video"
                        title_hint = re.sub(r'[^\w\-]', '_', meta.title)[:60]
                        return self._download_from_direct_url(
                            fmt.url, output_path,
                            f"{title_hint}_{video_id}", progress_callback
                        )
            raise RuntimeError("Could not obtain a fresh download URL. Please try again.")

        if format_id == "direct":
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path) or "download"
            if not os.path.splitext(filename)[1]:
                filename = f"{filename}.mp4"
            filename_base, ext = os.path.splitext(filename)
            output_file = os.path.join(output_path, f"{filename_base}_{int(time.time())}{ext}")

            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                response = requests.get(url, headers=headers, stream=True, timeout=60)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                progress = min(max(progress, 0.0), 99.0)
                                progress_callback(progress)
                progress_callback(100.0)
                return output_file
            except Exception as e:
                if os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except Exception:
                        pass
                raise e

        # Normalize format_id to prevent "Requested format is not available"
        if (format_id.startswith("best[ext=mp4][vcodec!=none]") or format_id == "best") and platform == "youtube":
            if self._ffmpeg_available():
                format_id = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            else:
                format_id = "best/bestvideo+bestaudio"
        elif "+" in format_id and not self._ffmpeg_available():
            format_id = "best"

        # Use unique template per download attempt (epoch suffix) to prevent
        # concurrent downloads to the same URL from colliding on the same file
        epoch_tag = int(time.time())
        output_template = os.path.join(output_path, f"%(title).80s_%(id)s_{epoch_tag}.%(ext)s")

        # Track fragment-based progress more accurately
        fragment_state = {'total_frags': 0, 'done_frags': 0}

        def hook(d):
            if d['status'] == 'downloading':
                # Prefer fragment-based progress for DASH/HLS streams
                frag_idx = d.get('fragment_index')
                frag_count = d.get('fragment_count')
                if frag_idx and frag_count and frag_count > 1:
                    fragment_state['total_frags'] = frag_count
                    fragment_state['done_frags'] = frag_idx
                    progress = (frag_idx / frag_count) * 100
                else:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        progress = (downloaded / total) * 100
                    else:
                        # Unknown total — show an indeterminate-ish ramp
                        progress = min(downloaded / (1024 * 1024), 95.0)  # 1% per MB
                # Clamp progress
                progress = min(max(progress, 0.0), 99.0)
                progress_callback(progress)
            elif d['status'] == 'finished':
                progress_callback(99.5)  # merging / post-processing may still happen

        # Build options with speed optimizations
        ydl_opts = self._base_ydl_opts(platform=platform)
        ydl_opts.update({
            'format': format_id,
            'merge_output_format': 'mp4',
            'outtmpl': output_template,
            'progress_hooks': [hook],
            'retries': 10,
            'fragment_retries': 10,
            'file_access_retries': 5,
            'extractor_retries': 5,
            'socket_timeout': 30,
            'continuedl': False,          # Disable resume to avoid HTTP 416 errors
            'nopart': False,              # Use .part files to avoid WinError 32 locking during audio/video merge
            'noresizebuffer': True,       # Don't resize download buffer (faster)
            'buffersize': 1024 * 1024,    # 1MB buffer for faster I/O
            'concurrent_fragment_downloads': 4,  # Download 4 fragments at once
            'overwrites': True,           # Overwrite partial files from failed attempts
        })
        if platform == "instagram":
            ydl_opts['noplaylist'] = False

        # Use aria2c as external downloader if available (much faster)
        if shutil.which("aria2c"):
            ydl_opts['external_downloader'] = 'aria2c'
            ydl_opts['external_downloader_args'] = {
                'aria2c': ['-x', '16', '-k', '1M', '-s', '16', '--min-split-size=1M']
            }

        last_error = None
        for attempt in range(1, 4):
            try:
                # Clean up any partial/temp files before each attempt to prevent HTTP 416
                self._cleanup_partial_files(output_path)

                # On retry for HTTP 416, add stronger anti-range options
                if attempt > 1:
                    ydl_opts['http_headers'] = {
                        **ydl_opts.get('http_headers', {}),
                        'Range': '',  # Clear any stale range header
                    }
                    # Regenerate unique template for each retry
                    retry_epoch = int(time.time())
                    ydl_opts['outtmpl'] = os.path.join(
                        output_path, f"%(title).80s_%(id)s_{retry_epoch}.%(ext)s"
                    )

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)

                    if not os.path.exists(filename):
                        # Try finding any file that starts with title in that dir
                        base, _ = os.path.splitext(filename)
                        for ext in ['.mp4', '.mkv', '.webm', '.m4a', '.mp3', '.opus', '.ogg', '.jpg', '.jpeg', '.png', '.webp', '.heic']:
                            if os.path.exists(base + ext):
                                filename = base + ext
                                break

                    progress_callback(100.0)
                    return filename
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                # If requested format is not available, gracefully fallback to best available
                if "requested format is not available" in err_str or "format is not available" in err_str:
                    if self._ffmpeg_available():
                        ydl_opts['format'] = "bestvideo+bestaudio/best"
                    else:
                        ydl_opts['format'] = "best"
                # If YouTube bot/cookie/player response error happened, switch to server-safe clients for next attempt
                elif platform == "youtube" and any(k in err_str for k in ["sign in", "bot", "cookie", "login", "429", "player response", "unable to download", "blocked", "confirm your age"]):
                    ydl_opts.pop('cookiesfrombrowser', None)
                    if attempt > 2:
                        ydl_opts.pop('cookiefile', None)
                    # Rotate through server-safe client combos on each retry
                    server_safe_clients = [
                        ['tv_embedded', 'mweb'],
                        ['tv_embedded'],
                        ['android', 'tv_embedded'],
                    ]
                    fb_clients = server_safe_clients[(attempt - 1) % len(server_safe_clients)]
                    ydl_opts['extractor_args'] = self._get_youtube_extractor_args()
                    ydl_opts['extractor_args']['youtube']['player_client'] = fb_clients
                    if self._ffmpeg_available():
                        ydl_opts['format'] = "bestvideo+bestaudio/best"
                    else:
                        ydl_opts['format'] = "best"
                # For HTTP 416, aggressively clean up and retry
                if '416' in err_str or 'range not satisfiable' in err_str:
                    self._cleanup_partial_files(output_path)
                if attempt == 3:
                    break
                time.sleep(attempt * 2)  # Slightly longer backoff between retries

        if last_error is not None:
            raise last_error
        raise RuntimeError("Download failed with unknown error.")

    def _cleanup_partial_files(self, output_path: str):
        """Remove partial/temp download files that can cause HTTP 416 errors."""
        if not os.path.exists(output_path):
            return
        # Patterns that indicate partial / in-progress downloads
        partial_suffixes = ('.part', '.ytdl', '.temp', '.part-Frag')
        for f in os.listdir(output_path):
            fpath = os.path.join(output_path, f)
            if os.path.isfile(fpath):
                # Match exact suffixes or fragment patterns like .part-Frag0, .part-Frag12
                is_partial = any(f.endswith(s) for s in partial_suffixes) or '.part-Frag' in f
                if is_partial:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass

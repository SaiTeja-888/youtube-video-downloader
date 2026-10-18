import re
from urllib.parse import urlparse, urlunparse


_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def normalize_media_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise ValueError("URL cannot be empty.")

    if not _SCHEME_RE.match(value):
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid http or https media URL.")

    return urlunparse(parsed._replace(fragment=""))


def hostname_for_url(url: str) -> str:
    parsed = urlparse(normalize_media_url(url))
    return parsed.netloc.lower().split("@")[-1].split(":")[0]

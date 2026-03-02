"""Shared helpers: logging, filename sanitizer, timestamp, image extension inference."""

from __future__ import annotations

import logging
import mimetypes
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SHANGHAI_TZ = timezone(timedelta(hours=8))
LOGGER_NAME = "wechat_to_md"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the package-level logger."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger


def get_logger() -> logging.Logger:
    """Return the package-level logger."""
    return logging.getLogger(LOGGER_NAME)


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Remove/replace filesystem-invalid characters and truncate."""
    sanitized = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name.strip())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized[:max_length].rstrip("_. ")


def format_timestamp(ts: int | str) -> str:
    """Convert Unix timestamp to 'YYYY-MM-DD HH:MM:SS' in Asia/Shanghai (UTC+8)."""
    try:
        ts_int = int(ts)
        dt = datetime.fromtimestamp(ts_int, tz=SHANGHAI_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def infer_image_extension(url: str, content_type: str | None = None) -> str:
    """
    Infer image file extension. Priority:
    1. wx_fmt= URL param (WeChat CDN specific)
    2. Content-Type header
    3. URL path extension
    4. Default 'png'
    """
    # 1. wx_fmt param
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "wx_fmt" in params:
            fmt = params["wx_fmt"][0].lower()
            if fmt in ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"):
                return "jpg" if fmt == "jpeg" else fmt
    except Exception:
        pass

    # 2. Content-Type header
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            ext = ext.lstrip(".")
            return "jpg" if ext == "jpeg" else ext

    # 3. URL path extension
    match = re.search(r"\.([a-zA-Z]{3,4})(?:\?|$|#)", url)
    if match:
        ext = match.group(1).lower()
        if ext in ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"):
            return "jpg" if ext == "jpeg" else ext

    # 4. Default
    return "png"


def read_urls_from_file(filepath: Path) -> list[str]:
    """Read URLs from a text file, one per line. Skip blanks and comments (#)."""
    urls: list[str] = []
    text = filepath.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http"):
            urls.append(line)
    return urls

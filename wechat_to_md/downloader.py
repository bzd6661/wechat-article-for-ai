"""Async image downloading with retry, concurrency control, and Content-Type inference."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx

from .utils import get_logger, infer_image_extension

_HEADERS = {
    "Referer": "https://mp.weixin.qq.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


@dataclass
class DownloadResult:
    remote_url: str
    local_path: str | None = None  # relative path like "images/img_001.png"
    error: str | None = None


async def download_single_image(
    client: httpx.AsyncClient,
    img_url: str,
    img_dir: Path,
    index: int,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
) -> DownloadResult:
    """Download a single image with retry logic."""
    logger = get_logger()

    # Normalize protocol-relative URLs
    url = img_url if not img_url.startswith("//") else f"https:{img_url}"

    async with semaphore:
        last_error: str = ""
        for attempt in range(max_retries):
            try:
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()

                content_type = resp.headers.get("content-type")
                ext = infer_image_extension(url, content_type)
                filename = f"img_{index:03d}.{ext}"
                filepath = img_dir / filename

                filepath.write_bytes(resp.content)

                return DownloadResult(
                    remote_url=img_url,
                    local_path=f"images/{filename}",
                )

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    delay = (attempt + 1) * 1.0
                    logger.debug(
                        f"Image download attempt {attempt + 1} failed for "
                        f"img_{index:03d}: {e}. Retrying in {delay:.0f}s..."
                    )
                    await asyncio.sleep(delay)

        logger.warning(f"Failed to download image {index}: {last_error}")
        return DownloadResult(remote_url=img_url, error=last_error)


async def download_all_images(
    img_urls: list[str],
    img_dir: Path,
    concurrency: int = 5,
    max_retries: int = 3,
) -> dict[str, str]:
    """
    Download all images concurrently.
    Returns {remote_url: local_relative_path} for successful downloads.
    """
    logger = get_logger()
    if not img_urls:
        return {}

    img_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
        tasks = [
            download_single_image(client, url, img_dir, i + 1, semaphore, max_retries)
            for i, url in enumerate(img_urls)
        ]
        results = await asyncio.gather(*tasks)

    url_map: dict[str, str] = {}
    succeeded = 0
    failed = 0
    for result in results:
        if result.local_path:
            url_map[result.remote_url] = result.local_path
            succeeded += 1
        else:
            failed += 1

    logger.info(f"Images: {succeeded} downloaded, {failed} failed (total: {len(img_urls)})")
    return url_map

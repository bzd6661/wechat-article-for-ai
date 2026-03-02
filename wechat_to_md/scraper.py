"""Camoufox page fetching with retry logic and CAPTCHA detection."""

from __future__ import annotations

import asyncio

from camoufox.async_api import AsyncCamoufox

from .errors import CaptchaError, NetworkError
from .utils import get_logger

# Indicators that WeChat is showing a verification/CAPTCHA page
_CAPTCHA_INDICATORS = [
    "js_verify",
    "verify_container",
    "环境异常",
    "请完成安全验证",
    "操作频繁",
]


def _is_captcha_page(html: str) -> bool:
    """Check if the HTML contains CAPTCHA/verification indicators."""
    return any(indicator in html for indicator in _CAPTCHA_INDICATORS)


async def fetch_page_html(
    url: str,
    headless: bool = True,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> str:
    """
    Fetch rendered HTML of a WeChat article using Camoufox.

    Uses networkidle instead of hardcoded sleep. Retries with exponential
    backoff on network/timeout errors. CaptchaError is never retried.
    """
    logger = get_logger()
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            async with AsyncCamoufox(headless=headless) as browser:
                page = await browser.new_page()
                logger.debug(f"Attempt {attempt + 1}/{max_retries}: navigating to {url}")

                await page.goto(url, wait_until="domcontentloaded")

                # Wait for the article content container
                try:
                    await page.wait_for_selector("#js_content", timeout=15000)
                except Exception:
                    pass  # Timeout not fatal — content may still be present

                # Wait for network to settle (replaces hardcoded sleep)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    # networkidle timeout is non-fatal; some pages have persistent connections
                    await asyncio.sleep(2)

                html = await page.content()

                # Validate: CAPTCHA?
                if _is_captcha_page(html):
                    raise CaptchaError(
                        "WeChat verification/CAPTCHA detected. "
                        "Try running with --no-headless to solve manually."
                    )

                # Validate: has content?
                if "#activity-name" not in html and "rich_media_title" not in html:
                    logger.warning("Page may not contain a valid article (no title element found)")

                return html

        except CaptchaError:
            raise  # Never retry CAPTCHAs

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.0f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed for {url}")

    raise NetworkError(f"Failed after {max_retries} attempts: {last_error}")

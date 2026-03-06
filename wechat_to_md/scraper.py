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

_ARTICLE_READY_SELECTORS = [
    "#js_content",
    "#js_article_content",
    "#js_image_content",
    ".rich_media_title",
]

_ARTICLE_CONTENT_INDICATORS = [
    'id="js_content"',
    'id="js_article_content"',
    'id="js_image_content"',
    "rich_media_title",
]


def _is_captcha_page(html: str) -> bool:
    """Check if the HTML contains CAPTCHA/verification indicators."""
    return any(indicator in html for indicator in _CAPTCHA_INDICATORS)


def _has_article_content(html: str) -> bool:
    """Check whether the HTML contains rendered article structure."""
    return any(indicator in html for indicator in _ARTICLE_CONTENT_INDICATORS)


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

                # Wait for one of the rendered article containers to appear.
                try:
                    await page.wait_for_function(
                        """(selectors) => selectors.some((selector) => document.querySelector(selector))""",
                        _ARTICLE_READY_SELECTORS,
                        timeout=15000,
                    )
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

                # Retry if WeChat only returned shell/meta content and the body never rendered.
                if not _has_article_content(html):
                    raise RuntimeError("Rendered article body not found")

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

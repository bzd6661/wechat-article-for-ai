"""CLI entry point: argparse, single/batch article processing."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from .converter import build_markdown, convert_html_to_markdown, replace_image_urls
from .downloader import download_all_images
from .errors import CaptchaError, NetworkError, ParseError, WechatToMdError
from .parser import extract_metadata, process_content
from .scraper import fetch_page_html
from .utils import get_logger, read_urls_from_file, sanitize_filename, setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat-to-md",
        description="Convert WeChat Official Account articles to Markdown with local images.",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more WeChat article URLs.",
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        help="Text file containing URLs (one per line, # for comments).",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("./output"),
        help="Output directory (default: ./output).",
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=5,
        help="Max concurrent image downloads (default: 5).",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image downloading; keep remote URLs in markdown.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window (useful for solving CAPTCHAs).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output directories.",
    )
    parser.add_argument(
        "--no-frontmatter",
        action="store_true",
        help="Use blockquote metadata instead of YAML frontmatter.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def validate_url(url: str) -> bool:
    """Check that URL is a WeChat article URL."""
    return url.startswith("https://mp.weixin.qq.com/")


async def process_single_article(
    url: str,
    output_dir: Path,
    headless: bool = True,
    download_images: bool = True,
    concurrency: int = 5,
    force: bool = False,
    use_frontmatter: bool = True,
) -> bool:
    """Process a single article URL end-to-end. Returns True on success."""
    logger = get_logger()
    logger.info(f"Processing: {url}")

    html = ""
    try:
        # 1. Fetch page
        html = await fetch_page_html(url, headless=headless)

        # 2. Parse
        soup = BeautifulSoup(html, "html.parser")
        meta = extract_metadata(soup, html, url=url)

        if not meta.title:
            raise ParseError(
                "Could not extract article title. "
                "Page may be a CAPTCHA or invalid article."
            )

        logger.info(f"Title: {meta.title}")
        if meta.author:
            logger.info(f"Author: {meta.author}")

        # 3. Process content
        parsed = process_content(soup)

        if not parsed.content_html.strip():
            raise ParseError("Article content is empty after processing.")

        # 4. Convert to markdown
        md = convert_html_to_markdown(parsed.content_html, parsed.code_blocks)

        # 5. Prepare output directory
        safe_title = sanitize_filename(meta.title)
        article_dir = output_dir / safe_title

        if article_dir.exists() and not force:
            logger.info(f"Skipping (already exists): {article_dir}")
            logger.info("Use --force to overwrite.")
            return True

        article_dir.mkdir(parents=True, exist_ok=True)

        # 6. Download images
        if download_images and parsed.image_urls:
            img_dir = article_dir / "images"
            url_map = await download_all_images(
                parsed.image_urls, img_dir, concurrency=concurrency
            )
            md = replace_image_urls(md, url_map)

        # 7. Build final markdown
        final_md = build_markdown(
            meta, md, parsed.media_references, use_frontmatter=use_frontmatter
        )

        # 8. Write output
        md_path = article_dir / f"{safe_title}.md"
        md_path.write_text(final_md, encoding="utf-8")

        logger.info(f"Saved: {md_path} ({len(final_md)} chars, {len(parsed.image_urls)} images)")
        return True

    except CaptchaError as e:
        logger.error(f"CAPTCHA: {e}")
        _save_debug_html(html, output_dir, url)
        return False

    except NetworkError as e:
        logger.error(f"Network error: {e}")
        return False

    except ParseError as e:
        logger.error(f"Parse error: {e}")
        _save_debug_html(html, output_dir, url)
        return False

    except WechatToMdError as e:
        logger.error(f"Error: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        _save_debug_html(html, output_dir, url)
        return False


def _save_debug_html(html: str, output_dir: Path, url: str) -> None:
    """Save raw HTML for debugging when parsing fails."""
    if not html:
        return
    logger = get_logger()
    debug_dir = output_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    suffix = sanitize_filename(url[-30:]) if len(url) > 30 else sanitize_filename(url)
    debug_path = debug_dir / f"debug_{suffix}.html"
    debug_path.write_text(html, encoding="utf-8")
    logger.info(f"Debug HTML saved: {debug_path}")


async def async_main(args: argparse.Namespace) -> int:
    """Main async entry point. Returns exit code."""
    logger = get_logger()

    # Collect URLs
    urls: list[str] = list(args.urls) if args.urls else []
    if args.file:
        if not args.file.exists():
            logger.error(f"File not found: {args.file}")
            return 1
        urls.extend(read_urls_from_file(args.file))

    if not urls:
        logger.error("No URLs provided. Use positional args or -f <file>.")
        return 1

    # Validate
    valid_urls: list[str] = []
    for url in urls:
        if validate_url(url):
            valid_urls.append(url)
        else:
            logger.warning(f"Skipping invalid URL: {url}")

    if not valid_urls:
        logger.error("No valid WeChat URLs found.")
        return 1

    logger.info(f"Processing {len(valid_urls)} article(s)...")

    # Process sequentially
    results: list[tuple[str, bool]] = []
    for url in valid_urls:
        success = await process_single_article(
            url=url,
            output_dir=args.output,
            headless=not args.no_headless,
            download_images=not args.no_images,
            concurrency=args.concurrency,
            force=args.force,
            use_frontmatter=not args.no_frontmatter,
        )
        results.append((url, success))

    # Summary
    total = len(results)
    succeeded = sum(1 for _, s in results if s)
    failed_urls = [u for u, s in results if not s]

    if total > 1:
        logger.info(f"Completed: {succeeded}/{total} articles")
        if failed_urls:
            logger.warning("Failed URLs:")
            for u in failed_urls:
                logger.warning(f"  - {u}")

    return 0 if not failed_urls else 1


def main() -> None:
    """Synchronous entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.urls and not args.file:
        parser.print_help()
        sys.exit(1)

    setup_logging(verbose=args.verbose)
    exit_code = asyncio.run(async_main(args))
    sys.exit(exit_code)

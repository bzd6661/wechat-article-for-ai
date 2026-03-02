"""MCP server exposing WeChat article conversion as tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .utils import setup_logging

mcp = FastMCP(name="wechat-to-md")


@mcp.tool()
async def convert_article(
    url: str,
    output_dir: str = "./output",
    download_images: bool = True,
    concurrency: int = 5,
    use_frontmatter: bool = True,
) -> str:
    """
    Convert a WeChat Official Account article to Markdown with local images.

    Args:
        url: WeChat article URL (must start with https://mp.weixin.qq.com/)
        output_dir: Output directory path (default: ./output)
        download_images: Whether to download images locally (default: True)
        concurrency: Max concurrent image downloads (default: 5)
        use_frontmatter: Use YAML frontmatter for metadata (default: True)

    Returns:
        Summary of the conversion result including output path.
    """
    # Lazy imports to avoid loading heavy deps at server startup
    from bs4 import BeautifulSoup

    from .converter import build_markdown, convert_html_to_markdown, replace_image_urls
    from .downloader import download_all_images
    from .errors import CaptchaError, NetworkError, ParseError
    from .parser import extract_metadata, process_content
    from .scraper import fetch_page_html
    from .utils import sanitize_filename

    logger = setup_logging()

    if not url.startswith("https://mp.weixin.qq.com/"):
        return f"Error: Invalid URL. Must start with https://mp.weixin.qq.com/. Got: {url}"

    try:
        html = await fetch_page_html(url, headless=True)
        soup = BeautifulSoup(html, "html.parser")
        meta = extract_metadata(soup, html, url=url)

        if not meta.title:
            return (
                "Error: Could not extract article title. "
                "The page may be showing a CAPTCHA or is not a valid article."
            )

        parsed = process_content(soup)
        md = convert_html_to_markdown(parsed.content_html, parsed.code_blocks)

        out = Path(output_dir)
        safe_title = sanitize_filename(meta.title)
        article_dir = out / safe_title
        article_dir.mkdir(parents=True, exist_ok=True)

        if download_images and parsed.image_urls:
            img_dir = article_dir / "images"
            url_map = await download_all_images(
                parsed.image_urls, img_dir, concurrency=concurrency
            )
            md = replace_image_urls(md, url_map)

        final_md = build_markdown(
            meta, md, parsed.media_references, use_frontmatter=use_frontmatter
        )

        md_path = article_dir / f"{safe_title}.md"
        md_path.write_text(final_md, encoding="utf-8")

        return (
            f"Success: Converted article.\n"
            f"  Title: {meta.title}\n"
            f"  Author: {meta.author}\n"
            f"  Date: {meta.publish_time}\n"
            f"  Output: {md_path}\n"
            f"  Images: {len(parsed.image_urls)}\n"
            f"  Size: {len(final_md)} chars"
        )

    except CaptchaError as e:
        return f"CaptchaError: {e}"
    except NetworkError as e:
        return f"NetworkError: {e}"
    except ParseError as e:
        return f"ParseError: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool()
async def batch_convert(
    urls: list[str],
    output_dir: str = "./output",
    download_images: bool = True,
    concurrency: int = 5,
) -> str:
    """
    Convert multiple WeChat articles to Markdown.

    Args:
        urls: List of WeChat article URLs.
        output_dir: Output directory path (default: ./output).
        download_images: Whether to download images locally (default: True).
        concurrency: Max concurrent image downloads per article (default: 5).

    Returns:
        Summary of batch conversion results.
    """
    results: list[str] = []
    succeeded = 0
    failed = 0

    for i, url in enumerate(urls, 1):
        result = await convert_article(
            url=url,
            output_dir=output_dir,
            download_images=download_images,
            concurrency=concurrency,
        )
        results.append(f"[{i}/{len(urls)}] {url}\n  {result.splitlines()[0]}")
        if result.startswith("Success"):
            succeeded += 1
        else:
            failed += 1

    summary = f"\nBatch complete: {succeeded}/{len(urls)} succeeded, {failed} failed.\n"
    return summary + "\n".join(results)


def run_server() -> None:
    """Run the MCP server with stdio transport."""
    setup_logging()
    mcp.run(transport="stdio")

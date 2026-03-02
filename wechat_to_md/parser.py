"""HTML parsing: metadata extraction, content processing, code block handling."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from .utils import format_timestamp, get_logger

# Regex to filter CSS counter garbage text leaked into code blocks
_CSS_COUNTER_RE = re.compile(r"^(?:[a-z]*ounter|content)\s*\(", re.IGNORECASE)
_LINE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")

# Publish time extraction patterns
_TIME_PATTERNS = [
    re.compile(r"""create_time\s*[:=]\s*['"](\d{10})['"]"""),
    re.compile(r"""create_time\s*[:=]\s*JsDecode\(\s*['"](\d{10})['"]\s*\)"""),
]

# Noise elements to remove from article content
_NOISE_SELECTORS = [
    "script",
    "style",
    ".qr_code_pc",
    ".reward_area",
    ".rich_media_tool",
    ".like_a_look_info",
    "#js_pc_qr_code",
    ".share_notice",
    ".reward_qrcode_area",
    ".js_underline_link_tooltip",
]


@dataclass
class ArticleMetadata:
    title: str = ""
    author: str = ""
    publish_time: str = ""
    source_url: str = ""


@dataclass
class CodeBlock:
    lang: str
    code: str


@dataclass
class MediaReference:
    """Embedded audio or video found in the article."""
    media_type: str  # 'audio' or 'video'
    name: str
    src: str = ""


@dataclass
class ParsedContent:
    content_html: str = ""
    code_blocks: list[CodeBlock] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    media_references: list[MediaReference] = field(default_factory=list)


def extract_publish_time(html: str) -> str:
    """Extract publish timestamp from raw HTML script variables."""
    for pattern in _TIME_PATTERNS:
        match = pattern.search(html)
        if match:
            return format_timestamp(match.group(1))
    return ""


def extract_metadata(soup: BeautifulSoup, html: str, url: str = "") -> ArticleMetadata:
    """Extract article metadata (title, author, publish time)."""
    title_el = soup.select_one("#activity-name")
    author_el = soup.select_one("#js_name")

    return ArticleMetadata(
        title=title_el.get_text(strip=True) if title_el else "",
        author=author_el.get_text(strip=True) if author_el else "",
        publish_time=extract_publish_time(html),
        source_url=url,
    )


def _is_css_garbage(line: str) -> bool:
    """Check if a code line is CSS counter garbage or pure line number."""
    stripped = line.strip()
    if not stripped:
        return False
    if _CSS_COUNTER_RE.match(stripped):
        return True
    if _LINE_NUMBER_RE.match(stripped):
        return True
    return False


def _extract_code_blocks(soup: BeautifulSoup) -> list[CodeBlock]:
    """Extract code blocks from WeChat's .code-snippet__fix elements."""
    logger = get_logger()
    blocks: list[CodeBlock] = []

    for snippet in soup.select(".code-snippet__fix"):
        # Remove line number elements
        for line_idx in snippet.select(".code-snippet__line-index"):
            line_idx.decompose()

        # Get language
        pre_el = snippet.select_one("pre[data-lang]")
        lang = pre_el.get("data-lang", "") if pre_el else ""

        # Collect code from <code> tags, filtering garbage
        lines: list[str] = []
        for code_el in snippet.select("code"):
            text = code_el.get_text()
            if not _is_css_garbage(text):
                lines.append(text)

        code = "\n".join(lines)
        if code.strip():
            blocks.append(CodeBlock(lang=str(lang), code=code))
            logger.debug(f"Extracted code block: lang={lang}, {len(code)} chars")

        # Replace the snippet element with a placeholder
        placeholder = soup.new_tag("p")
        placeholder.string = f"CODEBLOCK-PLACEHOLDER-{len(blocks) - 1}"
        snippet.replace_with(placeholder)

    return blocks


def _extract_media(soup: BeautifulSoup) -> list[MediaReference]:
    """Extract embedded audio/video references."""
    refs: list[MediaReference] = []

    # WeChat audio: <mpvoice> custom element
    for voice in soup.select("mpvoice"):
        name = voice.get("name", voice.get("voice_encode_fileid", "Audio"))
        refs.append(MediaReference(media_type="audio", name=str(name)))
        placeholder = soup.new_tag("p")
        placeholder.string = f"[Audio: {name}]"
        voice.replace_with(placeholder)

    # WeChat video: <mpvideo> custom element
    for video in soup.select("mpvideo"):
        title = video.get("data-title", video.get("title", "Video"))
        src = video.get("data-src", video.get("src", ""))
        refs.append(MediaReference(media_type="video", name=str(title), src=str(src)))
        placeholder = soup.new_tag("p")
        placeholder.string = f"[Video: {title}]"
        video.replace_with(placeholder)

    # iframe-based videos (e.g., Tencent Video)
    for iframe in soup.select("iframe"):
        src = str(iframe.get("src", ""))
        if any(domain in src for domain in ("v.qq.com", "player.bilibili", "youku.com")):
            refs.append(MediaReference(media_type="video", name="Embedded Video", src=src))
            placeholder = soup.new_tag("p")
            placeholder.string = f"[Video: Embedded Video]({src})"
            iframe.replace_with(placeholder)

    return refs


def process_content(soup: BeautifulSoup) -> ParsedContent:
    """
    Pre-process the article DOM: fix lazy images, extract code blocks,
    extract media, remove noise, collect image URLs.
    """
    logger = get_logger()
    content_el = soup.select_one("#js_content")
    if not content_el:
        logger.warning("No #js_content found in page")
        return ParsedContent()

    # 1. Fix lazy-loaded images
    for img in content_el.select("img[data-src]"):
        img["src"] = img["data-src"]

    # 2. Extract code blocks (replaces with placeholders)
    code_blocks = _extract_code_blocks(content_el)

    # 3. Extract audio/video
    media_refs = _extract_media(content_el)

    # 4. Remove noise elements
    for selector in _NOISE_SELECTORS:
        for el in content_el.select(selector):
            el.decompose()

    # 5. Collect image URLs (de-duplicated, order preserved)
    seen: set[str] = set()
    image_urls: list[str] = []
    for img in content_el.select("img[src]"):
        src = str(img.get("src", ""))
        if src and src not in seen:
            seen.add(src)
            image_urls.append(src)

    logger.debug(f"Found {len(image_urls)} unique images, {len(code_blocks)} code blocks")

    return ParsedContent(
        content_html=str(content_el),
        code_blocks=code_blocks,
        image_urls=image_urls,
        media_references=media_refs,
    )

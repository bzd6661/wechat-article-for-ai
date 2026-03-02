"""Markdown conversion: HTML→MD, frontmatter, image URL replacement."""

from __future__ import annotations

import re

import markdownify

from .parser import ArticleMetadata, CodeBlock, MediaReference

# HTML tags to convert (everything else is stripped)
_CONVERT_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "a", "img",
    "ul", "ol", "li", "blockquote", "br", "hr",
    "table", "thead", "tbody", "tr", "th", "td",
    "pre", "code", "sup", "sub", "del", "s",
]

_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_EXCESSIVE_NEWLINES = re.compile(r"\n{4,}")
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)


def convert_html_to_markdown(content_html: str, code_blocks: list[CodeBlock]) -> str:
    """Convert processed HTML to Markdown, restoring code block placeholders."""
    md = markdownify.markdownify(
        content_html,
        heading_style="ATX",
        bullets="-",
        convert=_CONVERT_TAGS,
    )

    # Restore code block placeholders
    for i, block in enumerate(code_blocks):
        placeholder = f"CODEBLOCK-PLACEHOLDER-{i}"
        lang = block.lang or ""
        replacement = f"\n```{lang}\n{block.code}\n```\n"
        md = md.replace(placeholder, replacement)

    # Cleanup
    md = md.replace("\u00a0", " ")  # non-breaking spaces
    md = _EXCESSIVE_NEWLINES.sub("\n\n\n", md)
    md = _TRAILING_SPACES.sub("", md)

    return md.strip()


def replace_image_urls(md: str, url_map: dict[str, str]) -> str:
    """Replace remote image URLs in markdown with local paths."""

    def _replace(match: re.Match) -> str:
        alt = match.group(1)
        url = match.group(2)
        local_path = url_map.get(url)
        if local_path:
            return f"![{alt}]({local_path})"
        return match.group(0)

    return _IMAGE_PATTERN.sub(_replace, md)


def _escape_yaml_string(s: str) -> str:
    """Escape a string for YAML frontmatter value."""
    if not s:
        return '""'
    # Quote if contains special chars
    if any(c in s for c in ':{}[]&*?|->!%@`#,"\'\n'):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def build_frontmatter(meta: ArticleMetadata) -> str:
    """Build YAML frontmatter block."""
    lines = ["---"]
    if meta.title:
        lines.append(f"title: {_escape_yaml_string(meta.title)}")
    if meta.author:
        lines.append(f"author: {_escape_yaml_string(meta.author)}")
    if meta.publish_time:
        lines.append(f"date: {_escape_yaml_string(meta.publish_time)}")
    if meta.source_url:
        lines.append(f"source: {_escape_yaml_string(meta.source_url)}")
    lines.append("---")
    return "\n".join(lines)


def build_markdown(
    meta: ArticleMetadata,
    body_md: str,
    media_refs: list[MediaReference] | None = None,
    use_frontmatter: bool = True,
) -> str:
    """Assemble the final markdown document with metadata and body."""
    parts: list[str] = []

    if use_frontmatter:
        parts.append(build_frontmatter(meta))
        parts.append("")
        if meta.title:
            parts.append(f"# {meta.title}")
            parts.append("")
    else:
        # Blockquote-style (original format)
        if meta.title:
            parts.append(f"# {meta.title}")
            parts.append("")
        info_lines: list[str] = []
        if meta.author:
            info_lines.append(f"> Author: {meta.author}")
        if meta.publish_time:
            info_lines.append(f"> Date: {meta.publish_time}")
        if meta.source_url:
            info_lines.append(f"> Source: {meta.source_url}")
        if info_lines:
            parts.extend(info_lines)
            parts.append("")
        parts.append("---")
        parts.append("")

    parts.append(body_md)

    # Append media references if any
    if media_refs:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("## Media References")
        parts.append("")
        for ref in media_refs:
            if ref.src:
                parts.append(f"- [{ref.media_type.title()}: {ref.name}]({ref.src})")
            else:
                parts.append(f"- {ref.media_type.title()}: {ref.name}")

    parts.append("")  # trailing newline
    return "\n".join(parts)

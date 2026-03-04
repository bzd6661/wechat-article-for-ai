# wechat-article-for-ai

[English](#english) | [中文](#中文)

---

## English

A modular Python tool that converts WeChat Official Account (微信公众号) articles into clean Markdown files with locally downloaded images. Designed for both human use (CLI) and AI agent integration (MCP server + SKILL.md).

### Features

- **Anti-detection scraping** — Uses [Camoufox](https://github.com/nichochar/camoufox) (stealth Firefox) to bypass WeChat's bot detection
- **Smart page loading** — `networkidle` wait instead of hardcoded sleep
- **Retry logic** — 3× exponential backoff for page fetching, 3× linear backoff for image downloads
- **CAPTCHA detection** — Explicit detection with actionable error messages
- **Batch processing** — Multiple URLs via args or file input
- **Image localization** — Concurrent async downloads with Content-Type based extension inference
- **Code block preservation** — Language detection, CSS counter garbage filtering
- **Media extraction** — Handles WeChat's `<mpvoice>` audio and `<mpvideo>` video elements
- **YAML frontmatter** — Structured metadata (title, author, date, source)
- **MCP server** — Expose as tools for any MCP-compatible AI client
- **SKILL.md** — Ready for Claude Code skill integration

### Installation

```bash
git clone https://github.com/bzd6661/wechat-article-for-ai.git
cd wechat-article-for-ai
pip install -r requirements.txt
```

> Camoufox browser will be auto-downloaded on first run.

### Usage

#### CLI — Single Article

```bash
python main.py "https://mp.weixin.qq.com/s/ARTICLE_ID"
```

#### CLI — Batch from File

```bash
python main.py -f urls.txt -o ./output -v
```

#### CLI Options

| Flag | Description |
|------|-------------|
| `urls` | One or more WeChat article URLs |
| `-f, --file FILE` | Text file with URLs (one per line, `#` for comments) |
| `-o, --output DIR` | Output directory (default: `./output`) |
| `-c, --concurrency N` | Max concurrent image downloads (default: 5) |
| `--no-images` | Skip image download, keep remote URLs |
| `--no-headless` | Show browser window (for solving CAPTCHAs) |
| `--force` | Overwrite existing output |
| `--no-frontmatter` | Use blockquote metadata instead of YAML frontmatter |
| `-v, --verbose` | Enable debug logging |

#### MCP Server

Run as an MCP server for AI tool integration:

```bash
python mcp_server.py
```

**Tools exposed:**
- `convert_article` — Convert a single WeChat article to Markdown
- `batch_convert` — Convert multiple articles in one call

**MCP client configuration** (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "wechat-to-md": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/wechat-article-for-ai"
    }
  }
}
```

### Output Structure

```
output/
  <article-title>/
    <article-title>.md
    images/
      img_001.png
      img_002.jpg
      ...
```

### Project Structure

```
wechat_to_md/
  __init__.py        # Package init, public API
  errors.py          # CaptchaError, NetworkError, ParseError
  utils.py           # Logging, filename sanitizer, timestamp, image ext inference
  scraper.py         # Camoufox + networkidle + retry with exponential backoff
  parser.py          # BeautifulSoup: metadata, code blocks, media, noise removal
  converter.py       # markdownify + YAML frontmatter + image URL replacement
  downloader.py      # httpx async + retry per image + Content-Type inference
  cli.py             # argparse CLI with batch support
  mcp_server.py      # FastMCP server with convert_article / batch_convert
main.py              # CLI entry point
mcp_server.py        # MCP server entry point
SKILL.md             # AI skill definition
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| CAPTCHA / verification page | Run with `--no-headless` to solve manually |
| Empty content | WeChat may be rate-limiting; wait and retry |
| Image download failures | Failed images keep remote URLs; re-run with `--force` |

### License

MIT

---

## 中文

一个模块化的 Python 工具，将微信公众号文章转换为干净的 Markdown 文件并下载图片到本地。同时支持人工使用（CLI）和 AI 智能体集成（MCP 服务器 + SKILL.md）。

### 功能特点

- **反检测抓取** — 使用 [Camoufox](https://github.com/nichochar/camoufox)（隐身 Firefox）绕过微信的反爬机制
- **智能页面等待** — 使用 `networkidle` 替代硬编码的 sleep
- **重试机制** — 页面加载 3 次指数退避重试，图片下载 3 次线性退避重试
- **验证码检测** — 明确识别验证码页面并给出可操作的错误提示
- **批量处理** — 支持多个 URL 参数或从文件读取
- **图片本地化** — 异步并发下载，基于 Content-Type 推断图片格式
- **代码块保留** — 自动检测编程语言，过滤 CSS 计数器垃圾文本
- **媒体提取** — 处理微信的 `<mpvoice>` 音频和 `<mpvideo>` 视频元素
- **YAML 元数据** — 结构化的 frontmatter（标题、作者、日期、来源）
- **MCP 服务器** — 暴露为工具，供任何 MCP 兼容的 AI 客户端调用
- **SKILL.md** — 可直接作为 Claude Code 技能使用

### 安装

```bash
git clone https://github.com/bzd6661/wechat-article-for-ai.git
cd wechat-article-for-ai
pip install -r requirements.txt
```

> Camoufox 浏览器会在首次运行时自动下载。

### 使用方法

#### CLI — 单篇文章

```bash
python main.py "https://mp.weixin.qq.com/s/文章ID"
```

#### CLI — 批量转换

```bash
python main.py -f urls.txt -o ./output -v
```

#### CLI 参数

| 参数 | 说明 |
|------|------|
| `urls` | 一个或多个微信文章链接 |
| `-f, --file 文件` | 包含 URL 的文本文件（每行一个，`#` 为注释） |
| `-o, --output 目录` | 输出目录（默认：`./output`） |
| `-c, --concurrency N` | 图片下载最大并发数（默认：5） |
| `--no-images` | 跳过图片下载，保留远程链接 |
| `--no-headless` | 显示浏览器窗口（用于手动解决验证码） |
| `--force` | 覆盖已有的输出目录 |
| `--no-frontmatter` | 使用引用块格式的元数据，而非 YAML frontmatter |
| `-v, --verbose` | 启用调试日志 |

#### MCP 服务器

作为 MCP 服务器运行，供 AI 工具集成：

```bash
python mcp_server.py
```

**暴露的工具：**
- `convert_article` — 转换单篇微信文章为 Markdown
- `batch_convert` — 批量转换多篇文章

**MCP 客户端配置**（如 `claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "wechat-to-md": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/wechat-article-for-ai"
    }
  }
}
```

### 输出结构

```
output/
  <文章标题>/
    <文章标题>.md
    images/
      img_001.png
      img_002.jpg
      ...
```

### 项目结构

```
wechat_to_md/
  __init__.py        # 包初始化，公共 API
  errors.py          # CaptchaError, NetworkError, ParseError
  utils.py           # 日志、文件名清理、时间戳、图片格式推断
  scraper.py         # Camoufox + networkidle + 指数退避重试
  parser.py          # BeautifulSoup：元数据、代码块、媒体、噪音移除
  converter.py       # markdownify + YAML frontmatter + 图片 URL 替换
  downloader.py      # httpx 异步 + 逐图重试 + Content-Type 推断
  cli.py             # argparse CLI，支持批量处理
  mcp_server.py      # FastMCP 服务器
main.py              # CLI 入口
mcp_server.py        # MCP 服务器入口
SKILL.md             # AI 技能定义文件
```

### 常见问题

| 问题 | 解决方法 |
|------|----------|
| 出现验证码 / 环境异常 | 使用 `--no-headless` 手动解决验证码 |
| 内容为空 | 微信可能在限流，等几分钟再试 |
| 图片下载失败 | 失败的图片会保留远程链接，用 `--force` 重新运行 |

### 许可证

MIT

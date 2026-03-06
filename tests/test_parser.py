from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from wechat_to_md.converter import convert_html_to_markdown
from wechat_to_md.parser import extract_metadata, process_content
from wechat_to_md.scraper import _has_article_content


OLD_HTML = """
<html>
  <head>
    <meta name="author" content="Legacy Author">
  </head>
  <body>
    <h2 id="activity-name">Legacy Title</h2>
    <a id="js_name">Legacy Author</a>
    <div id="js_content">
      <p>Hello legacy world.</p>
      <div class="reward_area">Reward</div>
    </div>
    <script>var create_time = '1700000000';</script>
  </body>
</html>
"""


NEW_HTML = """
<html>
  <head>
    <meta property="og:title" content="Modern Title">
    <meta name="author" content="Modern Author">
  </head>
  <body>
    <div id="js_article_content" class="rich_media_area_primary">
      <div class="rich_media_area_primary_inner">
        <div id="js_content">
          <div id="js_image_content" class="image_content">
            <h1 class="rich_media_title">Modern Title</h1>
            <p id="js_image_desc" class="share_notice js_underline_content">
              First paragraph.<br><br>Second paragraph.
            </p>
            <div>
              <div class="reward_area">Reward block</div>
            </div>
            <div class="rich_media_tool">Tool block</div>
            <div class="rich_media_meta_list rich_media_meta_list_combine image_rich_media_meta_list">
              <span id="js_ip_wording">北京</span>
              <span id="publish_time">18 hours ago</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <script>var create_time = '1700000001';</script>
  </body>
</html>
"""


class ParserRegressionTests(unittest.TestCase):
    def test_extract_metadata_from_legacy_dom(self) -> None:
        soup = BeautifulSoup(OLD_HTML, "html.parser")

        meta = extract_metadata(soup, OLD_HTML, url="https://example.com/legacy")

        self.assertEqual(meta.title, "Legacy Title")
        self.assertEqual(meta.author, "Legacy Author")
        self.assertEqual(meta.source_url, "https://example.com/legacy")
        self.assertTrue(meta.publish_time)

    def test_extract_and_clean_modern_dom(self) -> None:
        soup = BeautifulSoup(NEW_HTML, "html.parser")

        meta = extract_metadata(soup, NEW_HTML, url="https://example.com/modern")
        parsed = process_content(soup)
        markdown = convert_html_to_markdown(parsed.content_html, parsed.code_blocks)

        self.assertEqual(meta.title, "Modern Title")
        self.assertEqual(meta.author, "Modern Author")
        self.assertIn("First paragraph.", markdown)
        self.assertIn("Second paragraph.", markdown)
        self.assertNotIn("北京", markdown)
        self.assertNotIn("18 hours ago", markdown)
        self.assertNotIn("Reward block", markdown)
        self.assertNotIn("Modern Title", markdown)

    def test_article_content_detection_distinguishes_shell_page(self) -> None:
        self.assertTrue(_has_article_content(NEW_HTML))
        self.assertFalse(_has_article_content(
            '<html><head><meta property="og:title" content="Only Meta"></head><body></body></html>'
        ))


if __name__ == "__main__":
    unittest.main()

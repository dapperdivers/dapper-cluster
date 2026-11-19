import unittest
from unittest import mock

from helpers import load_module, load_script

vl = load_module("vaultlib")
ri = load_script("reading-inbox.py")
rp = load_script("reading-process.py")

ARTICLE_HTML = """
<html><head><title>ignored</title><style>p { color: red; }</style></head>
<body>
<nav><a href="/home">Home</a></nav>
<h1>Growing tomatoes</h1>
<p>Tomatoes need   <b>sun</b> and
steady water. See the <a href="https://example.com/guide">full guide</a>.</p>
<script>alert("tracking");</script>
<h2>What you need</h2>
<ul><li>Seeds</li><li>Compost</li></ul>
<p><a href="https://example.com/photo"><img src="photo.jpg"></a></p>
<pre>line one
  line two</pre>
</body></html>
"""

ENTRY = {
    "id": 4711,
    "title": "Growing  tomatoes\nin small spaces",
    "url": "https://example.com/tomatoes",
    "author": "A. Gardener",
    "published_at": "2024-05-06T07:08:09Z",
    "feed": {"title": 'The "Example" Garden Blog', "category": {"title": "Home & Garden"}},
}


class ToText(unittest.TestCase):
    def setUp(self):
        self.text = ri.to_text(ARTICLE_HTML)

    def test_headings_move_one_level_down(self):
        self.assertIn("## Growing tomatoes", self.text)
        self.assertIn("### What you need", self.text)

    def test_list_items_become_bullets(self):
        self.assertIn("- Seeds\n- Compost", self.text)

    def test_links_become_markdown_links(self):
        self.assertIn("[full guide](https://example.com/guide)", self.text)

    def test_script_style_and_nav_are_dropped(self):
        for gone in ("alert", "tracking", "color: red", "Home"):
            self.assertNotIn(gone, self.text)

    def test_link_around_only_an_image_is_dropped(self):
        self.assertNotIn("example.com/photo", self.text)
        self.assertNotIn("[]", self.text)

    def test_whitespace_is_collapsed_outside_pre(self):
        self.assertIn("Tomatoes need sun and steady water.", self.text)
        self.assertIn("```\nline one\n  line two\n```", self.text)
        self.assertNotIn("\n\n\n", self.text)
        self.assertEqual(self.text, self.text.strip())

    def test_no_tags_left(self):
        self.assertNotRegex(self.text, r"</?[a-z][a-z0-9]*[ >]")

    def test_empty_input(self):
        self.assertEqual(ri.to_text(None), "")
        self.assertEqual(ri.to_text(""), "")

    def test_malformed_html_still_gives_the_text(self):
        text = ri.to_text("<p>Unclosed <b>bold <a href='https://example.com/x'>link<p>Next &amp; last</div></ul><li>item")
        for kept in ("Unclosed", "bold", "link", "Next & last", "item"):
            self.assertIn(kept, text)
        self.assertNotIn("<", text)

    def test_unclosed_script_does_not_leak_its_code(self):
        self.assertNotIn("secret", ri.to_text("<p>Before</p><script>var secret = 1;"))

    def test_parser_failure_falls_back_to_stripping_tags(self):
        with mock.patch.object(ri.Text, "feed", side_effect=AssertionError("parser bug")):
            text = ri.to_text("<p>Soil &amp; water</p>\n<p>and   light</p>")
        self.assertEqual(text, "Soil & water and light")


class SafeName(unittest.TestCase):
    def test_characters_obsidian_and_filesystems_reject_are_replaced(self):
        self.assertEqual(ri.safe_name('Soil: acid/alkaline? [part #1] "quoted" <a|b> x^2 c\\d *'),
                         "Soil acid alkaline part 1 quoted a b x 2 c d")

    def test_whitespace_is_collapsed(self):
        self.assertEqual(ri.safe_name("  Raised \t beds\nin  spring "), "Raised beds in spring")

    def test_long_titles_are_cut_at_90_characters(self):
        name = ri.safe_name("word " * 40)
        self.assertLessEqual(len(name), 90)
        self.assertFalse(name.endswith(" "))

    def test_trailing_dots_are_dropped(self):
        self.assertEqual(ri.safe_name("To be continued..."), "To be continued")

    def test_empty_titles(self):
        for title in (None, "", "   ", "???", "..."):
            with self.subTest(title=title):
                self.assertEqual(ri.safe_name(title), "Untitled")


class NoteFor(unittest.TestCase):
    def setUp(self):
        self.body_text = "## Growing tomatoes\n\nTomatoes need sun."
        self.note = ri.note_for(ENTRY, self.body_text, truncated=False)

    def test_frontmatter_fields(self):
        fm = vl.parse_frontmatter(self.note)
        self.assertEqual(fm["type"], "article")
        self.assertEqual(fm["source"], "miniflux")
        self.assertEqual(fm["status"], "inbox")
        self.assertEqual(fm["url"], "https://example.com/tomatoes")
        self.assertEqual(fm["published"], "2024-05-06")
        self.assertEqual(fm["miniflux_id"], "4711")
        self.assertEqual(fm["category"], "Home & Garden")
        self.assertEqual(fm["tags"], ["reading", "reading/home-garden"])
        self.assertRegex(fm["created"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        self.assertIn("Growing tomatoes in small spaces", fm["description"])
        self.assertNotIn("processed", fm)

    def test_quotes_in_the_feed_title_are_escaped(self):
        self.assertIn('feed: "The \\"Example\\" Garden Blog"', self.note)

    def test_title_and_source_line(self):
        self.assertIn("\n# Growing tomatoes in small spaces\n", self.note)
        self.assertIn("> [Original](https://example.com/tomatoes) · The \"Example\" Garden Blog"
                      " · 2024-05-06 · A. Gardener\n", self.note)

    def test_sections_are_in_order_and_the_article_is_last(self):
        notes, article = self.note.index("\n## My notes\n"), self.note.index("\n## Article\n")
        self.assertLess(notes, article)
        self.assertTrue(self.note.endswith("\n## Article\n\n" + self.body_text + "\n"))

    def test_reading_process_finds_the_article_text_again(self):
        _, body, _ = vl.split_frontmatter(self.note)
        self.assertEqual(rp.article_text(body), self.body_text)

    def test_truncated_note_says_so(self):
        note = ri.note_for(ENTRY, self.body_text, truncated=True)
        self.assertIn(f"*(Cut at {ri.MAX_CHARS} characters;", note)
        self.assertNotIn("Cut at", self.note)

    def test_entry_with_the_bare_minimum(self):
        note = ri.note_for({"id": 1}, "", truncated=False)
        fm = vl.parse_frontmatter(note)
        self.assertEqual(fm["miniflux_id"], "1")
        self.assertEqual(fm["tags"], ["reading"])
        self.assertIn("\n# Untitled\n", note)
        self.assertIn("\n## Article\n\n*(The feed carried no text for this article; open the original.)*\n", note)


if __name__ == "__main__":
    unittest.main()

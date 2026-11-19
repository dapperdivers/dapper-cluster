import unittest

from helpers import load_module, load_script

vl = load_module("vaultlib")
rp = load_script("reading-process.py")

ARTICLE = "## Growing tomatoes\n\nTomatoes need sun and steady water.\n\n## My notes on soil\n\nNot the notes section."

NOTE = f"""---
created: 2024-05-07T08:00:00-05:00
type: article
status: inbox
tags: [reading, reading/garden]
description: "Article starred in Miniflux: Growing tomatoes."
---

# Growing tomatoes

> [Original](https://example.com/tomatoes) · Example Garden Blog

## My notes

Try this on the balcony.

## Article

{ARTICLE}
"""

RESULT = {
    "summary": ["Tomatoes need six hours of sun.", "Water at the base, not the leaves."],
    "why": "Fits the balcony garden plan.",
    "related": ["Garden/Balcony plan.md", "Garden/Watering.md"],
    "folder": "Garden",
    "ideas": [{"claim": "Steady watering matters more than volume.",
               "quote": "Tomatoes need sun and steady water."}],
    "tags": ["tomatoes", "reading"],
}
EMPTY = {"summary": ["Nothing readable."], "why": "", "related": [], "folder": "", "ideas": [], "tags": []}


class ArticleText(unittest.TestCase):
    def test_text_after_the_article_heading(self):
        _, body, _ = vl.split_frontmatter(NOTE)
        self.assertEqual(rp.article_text(body), ARTICLE)

    def test_no_article_section(self):
        self.assertEqual(rp.article_text("\n# Title\n\n## My notes\n\nSomething.\n"), "")

    def test_heading_must_be_a_line_of_its_own(self):
        self.assertEqual(rp.article_text("\n# Title\n\n## Article ideas\n\nSomething.\n"), "")


class Digest(unittest.TestCase):
    def test_full_result(self):
        self.assertEqual(rp.digest(RESULT, "2024-05-08"), "\n".join([
            "## Digest",
            "",
            "*Written by the reading-processor agent on 2024-05-08. Check it against the article below.*",
            "",
            "- Tomatoes need six hours of sun.",
            "- Water at the base, not the leaves.",
            "",
            "**Why it matters:** Fits the balcony garden plan.",
            "",
            "**Related notes:** [[Garden/Balcony plan]], [[Garden/Watering]]",
            "",
            "**Suggested folder:** `Garden`",
            "",
            "**Ideas worth a note of their own:**",
            "",
            "- Steady watering matters more than volume.",
            "  > Tomatoes need sun and steady water.",
            "",
        ]))

    def test_empty_parts_are_left_out(self):
        text = rp.digest(EMPTY, "2024-05-08")
        self.assertIn("- Nothing readable.\n", text)
        for gone in ("Why it matters", "Related notes", "Suggested folder", "Ideas worth"):
            self.assertNotIn(gone, text)


class Apply(unittest.TestCase):
    def setUp(self):
        self.new = rp.apply(NOTE, RESULT, "2024-05-08")

    def test_digest_lands_above_my_notes(self):
        digest, notes = self.new.index("\n## Digest\n"), self.new.index("\n## My notes\n")
        self.assertLess(self.new.index("\n# Growing tomatoes\n"), digest)
        self.assertLess(digest, notes)
        self.assertLess(notes, self.new.index("\n## Article\n"))
        self.assertIn(rp.digest(RESULT, "2024-05-08") + "\n## My notes\n", self.new)

    def test_article_text_and_own_notes_are_unchanged(self):
        _, body, _ = vl.split_frontmatter(self.new)
        self.assertEqual(rp.article_text(body), ARTICLE)
        self.assertIn("\n## My notes\n\nTry this on the balcony.\n\n## Article\n", self.new)

    def test_removing_the_digest_gives_back_the_original_body(self):
        _, old_body, _ = vl.split_frontmatter(NOTE)
        _, new_body, _ = vl.split_frontmatter(self.new)
        self.assertEqual(new_body.replace(rp.digest(RESULT, "2024-05-08") + "\n", ""), old_body)

    def test_processed_is_added_and_other_frontmatter_kept(self):
        old, new = vl.parse_frontmatter(NOTE), vl.parse_frontmatter(self.new)
        self.assertEqual(new["processed"], "2024-05-08")
        self.assertEqual(new["status"], "inbox")
        for key in ("created", "type", "description"):
            self.assertEqual(new[key], old[key])

    def test_tags_are_merged_without_repeats(self):
        self.assertEqual(vl.parse_frontmatter(self.new)["tags"], ["reading", "reading/garden", "tomatoes"])

    def test_second_apply_returns_none(self):
        self.assertIsNone(rp.apply(self.new, RESULT, "2024-05-09"))

    def test_note_with_processed_but_no_digest_is_left_alone(self):
        self.assertIsNone(rp.apply(NOTE.replace("status: inbox\n", "status: inbox\nprocessed: 2024-05-01\n"),
                                   RESULT, "2024-05-08"))

    def test_note_with_a_digest_but_no_processed_is_left_alone(self):
        self.assertIsNone(rp.apply(NOTE.replace("## My notes\n", "## Digest\n\nOld.\n\n## My notes\n"),
                                   RESULT, "2024-05-08"))

    def test_note_without_frontmatter_is_left_alone(self):
        self.assertIsNone(rp.apply("# Growing tomatoes\n\n## Article\n\nText.\n", RESULT, "2024-05-08"))

    def test_without_my_notes_the_digest_goes_above_the_article(self):
        new = rp.apply(NOTE.replace("## My notes\n\nTry this on the balcony.\n\n", ""), EMPTY, "2024-05-08")
        self.assertLess(new.index("\n## Digest\n"), new.index("\n## Article\n"))
        _, body, _ = vl.split_frontmatter(new)
        self.assertEqual(rp.article_text(body), ARTICLE)

    def test_without_either_section_the_digest_goes_at_the_end(self):
        new = rp.apply("---\ntype: article\n---\n\n# Title\n\nSome text.\n", EMPTY, "2024-05-08")
        self.assertTrue(new.endswith("Some text.\n\n" + rp.digest(EMPTY, "2024-05-08")))

    def test_no_tags_leaves_the_tags_line_alone(self):
        new = rp.apply(NOTE, EMPTY, "2024-05-08")
        self.assertIn("\ntags: [reading, reading/garden]\n", new)


if __name__ == "__main__":
    unittest.main()

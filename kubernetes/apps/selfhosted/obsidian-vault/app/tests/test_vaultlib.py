import unittest

from helpers import load_module

vl = load_module("vaultlib")

NOTE = """---
created: 2024-01-02
type: recipe
title: "Sourdough: a first loaf"
tags: [baking, 'bread', "weekend"]
aliases:
  - First loaf
  - "Starter bread"
empty:
---

# Sourdough

Mix flour and water.
"""


class SplitFrontmatter(unittest.TestCase):
    def test_splits_frontmatter_from_body(self):
        fm, body, stop = vl.split_frontmatter(NOTE)
        self.assertTrue(fm.startswith("created: 2024-01-02\n"))
        self.assertTrue(fm.endswith("empty:\n"))
        self.assertEqual(body, "\n# Sourdough\n\nMix flour and water.\n")
        self.assertEqual(NOTE[stop:], body)

    def test_rebuilding_gives_the_original_text(self):
        fm, body, _ = vl.split_frontmatter(NOTE)
        self.assertEqual("---\n" + fm + "---\n" + body, NOTE)

    def test_no_frontmatter(self):
        text = "# Just a heading\n\n---\n\nA rule, not frontmatter.\n"
        self.assertEqual(vl.split_frontmatter(text), (None, text, 0))

    def test_unterminated_frontmatter(self):
        text = "---\ntype: recipe\n\n# Heading\n"
        self.assertEqual(vl.split_frontmatter(text), (None, text, 0))

    def test_frontmatter_only_without_trailing_newline(self):
        fm, body, stop = vl.split_frontmatter("---\ntype: recipe\n---")
        self.assertEqual((fm, body), ("type: recipe\n", ""))
        self.assertEqual(stop, len("---\ntype: recipe\n---"))

    def test_empty_text(self):
        self.assertEqual(vl.split_frontmatter(""), (None, "", 0))


class ParseFrontmatter(unittest.TestCase):
    def test_scalars_and_lists(self):
        fm = vl.parse_frontmatter(NOTE)
        self.assertEqual(fm["created"], "2024-01-02")
        self.assertEqual(fm["type"], "recipe")
        self.assertEqual(fm["title"], "Sourdough: a first loaf")
        self.assertEqual(fm["tags"], ["baking", "bread", "weekend"])
        self.assertEqual(fm["aliases"], ["First loaf", "Starter bread"])
        self.assertEqual(fm["empty"], [])

    def test_no_frontmatter_is_an_empty_dict(self):
        self.assertEqual(vl.parse_frontmatter("# Heading\n\ntype: recipe\n"), {})

    def test_body_is_not_parsed(self):
        fm = vl.parse_frontmatter("---\ntype: recipe\n---\nstatus: done\n- item\n")
        self.assertEqual(fm, {"type": "recipe"})

    def test_list_item_under_a_scalar_is_ignored(self):
        fm = vl.parse_frontmatter("---\ntype: recipe\n  - stray\n---\n")
        self.assertEqual(fm, {"type": "recipe"})


class JsonFromText(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(vl.json_from_text('{"folder": "Garden"}'), {"folder": "Garden"})

    def test_object_inside_prose_and_a_code_fence(self):
        text = 'Here is the answer:\n```json\n{"folder": "Garden", "related": []}\n```\nDone.'
        self.assertEqual(vl.json_from_text(text), {"folder": "Garden", "related": []})

    def test_last_object_wins(self):
        text = 'Draft: {"folder": "Kitchen"}\nFinal: {"folder": "Garden"}'
        self.assertEqual(vl.json_from_text(text), {"folder": "Garden"})

    def test_nested_object_is_not_taken_for_the_answer(self):
        text = '{"folder": "Garden", "meta": {"folder": "Kitchen"}}'
        self.assertEqual(vl.json_from_text(text)["folder"], "Garden")

    def test_stray_braces_are_skipped(self):
        text = 'Use {curly} braces like {this}. {"ok": true} and then {broken'
        self.assertEqual(vl.json_from_text(text), {"ok": True})

    def test_no_object_raises(self):
        for text in ("", "no json here", "[1, 2, 3]", "{not json}"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                vl.json_from_text(text)


class YamlStr(unittest.TestCase):
    def test_quotes_a_plain_string(self):
        self.assertEqual(vl.yaml_str("Tomato notes"), '"Tomato notes"')

    def test_escapes_quotes_and_backslashes(self):
        self.assertEqual(vl.yaml_str('say "hi" \\ bye'), '"say \\"hi\\" \\\\ bye"')

    def test_collapses_whitespace_to_one_line(self):
        self.assertEqual(vl.yaml_str("  two\nlines\tand   gaps "), '"two lines and gaps"')

    def test_non_strings(self):
        self.assertEqual(vl.yaml_str(42), '"42"')
        self.assertEqual(vl.yaml_str(""), '""')


class Wikilink(unittest.TestCase):
    def test_drops_the_md_extension(self):
        self.assertEqual(vl.wikilink("Garden/Tomatoes.md"), "[[Garden/Tomatoes]]")

    def test_label(self):
        self.assertEqual(vl.wikilink("Garden/Tomatoes.md", "tomatoes"), "[[Garden/Tomatoes|tomatoes]]")

    def test_other_extensions_are_kept(self):
        self.assertEqual(vl.wikilink("Attachments/plan.pdf"), "[[Attachments/plan.pdf]]")


if __name__ == "__main__":
    unittest.main()

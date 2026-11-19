"""Only the four pure helpers are tested here: the rest of feed-sorter.py is being reworked."""
import re
import unittest

from helpers import load_script

fs = load_script("feed-sorter.py")

PROFILE = f"""---
type: reference
tags:
  - system/feed-sorter
---

# Feed Interests

- a bullet before any section is ignored

## Interests

- vegetable gardening, raised beds, compost
* bread baking, sourdough starters
- {fs.PLACEHOLDER} one topic you want to see
Not a bullet, so ignored.

## Noise

  - giveaways, discount codes, sponsored posts
- {fs.PLACEHOLDER} one kind of entry you never want

## Watchlist

Names that are always kept.

- Acme Seeds
- C++

## Something else

- not a known section
"""


def entry(title, content=""):
    return {"title": title, "content": content}


def patterns(names):
    """The same whole-word patterns main() builds from the watchlist."""
    return [(n, re.compile(r"(?<!\w)" + re.escape(n) + r"(?!\w)", re.I)) for n in names]


class ReadProfile(unittest.TestCase):
    def test_sections_and_bullets(self):
        self.assertEqual(fs.read_profile(PROFILE), {
            "interests": ["vegetable gardening, raised beds, compost", "bread baking, sourdough starters"],
            "noise": ["giveaways, discount codes, sponsored posts"],
            "watchlist": ["Acme Seeds", "C++"],
        })

    def test_placeholder_bullets_are_ignored(self):
        profile = fs.read_profile(PROFILE)
        self.assertFalse([b for bullets in profile.values() for b in bullets if fs.PLACEHOLDER in b])

    def test_the_starter_note_has_nothing_to_score_against(self):
        self.assertEqual(fs.read_profile(fs.STARTER), {"interests": [], "noise": [], "watchlist": []})

    def test_note_without_frontmatter_or_sections(self):
        self.assertEqual(fs.read_profile("## interests\n- soup\n")["interests"], ["soup"])
        self.assertEqual(fs.read_profile("Just prose.\n"), {"interests": [], "noise": [], "watchlist": []})


class IsEnglish(unittest.TestCase):
    def test_english_text(self):
        self.assertTrue(fs.is_english(entry(
            "How to build a raised bed for your vegetables",
            "<p>A raised bed is the easiest way to start growing vegetables in a small garden, "
            "and you can build one from a few planks in an afternoon.</p>")))

    def test_other_language(self):
        self.assertFalse(fs.is_english(entry(
            "Cómo preparar pan casero con masa madre",
            "<p>Mezcla la harina con el agua y deja reposar la masa durante toda la noche. "
            "Por la mañana, amasa de nuevo y hornea el pan hasta que esté dorado y crujiente.</p>")))

    def test_short_text_gets_the_benefit_of_the_doubt(self):
        self.assertTrue(fs.is_english(entry("Pan casero con masa madre")))

    def test_markup_is_not_counted_as_words(self):
        self.assertTrue(fs.is_english(entry("Zzz", "<div class='the of and to in is for on with that'>qq</div>")))


class TitleKey(unittest.TestCase):
    def test_case_punctuation_and_spacing_do_not_matter(self):
        self.assertEqual(fs.title_key(entry("  Raised Beds: A Beginner's Guide! ")), "raised beds a beginner s guide")
        self.assertEqual(fs.title_key(entry("Raised beds - a beginner's guide")),
                         fs.title_key(entry("RAISED BEDS: A BEGINNER'S GUIDE")))

    def test_different_titles_have_different_keys(self):
        self.assertNotEqual(fs.title_key(entry("Raised beds, part 1")), fs.title_key(entry("Raised beds, part 2")))

    def test_title_with_no_letters_or_digits(self):
        self.assertEqual(fs.title_key(entry("?!")), "")


class WatchHit(unittest.TestCase):
    def setUp(self):
        self.patterns = patterns(["Acme", "Seed Co", "C++"])

    def test_match_in_the_title_is_case_insensitive(self):
        self.assertEqual(fs.watch_hit(entry("ACME opens a new nursery"), self.patterns), "Acme")
        self.assertEqual(fs.watch_hit(entry("News from acme."), self.patterns), "Acme")

    def test_match_in_the_text(self):
        self.assertEqual(fs.watch_hit(entry("Nursery news", "<p>Bought by <b>Seed Co</b> last week</p>"),
                                      self.patterns), "Seed Co")

    def test_whole_words_only(self):
        self.assertIsNone(fs.watch_hit(entry("Acmeology and macme are not Acme2"), self.patterns))
        self.assertIsNone(fs.watch_hit(entry("Seed Company results"), self.patterns))

    def test_names_with_punctuation(self):
        self.assertEqual(fs.watch_hit(entry("Why C++ is still around"), self.patterns), "C++")
        self.assertIsNone(fs.watch_hit(entry("Why C is still around"), self.patterns))

    def test_first_name_in_watchlist_order_wins(self):
        self.assertEqual(fs.watch_hit(entry("Seed Co and Acme merge"), self.patterns), "Acme")

    def test_no_match_and_empty_watchlist(self):
        self.assertIsNone(fs.watch_hit(entry("Compost basics"), self.patterns))
        self.assertIsNone(fs.watch_hit(entry("Acme"), []))


if __name__ == "__main__":
    unittest.main()

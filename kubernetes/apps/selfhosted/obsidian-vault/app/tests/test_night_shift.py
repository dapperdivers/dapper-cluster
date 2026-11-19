"""The pure parts of night-shift.py: the pipeline-health lines and the feeds-digest request.

Everything here works on throwaway folders and fixed times; nothing calls an agent.
"""
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import load_module, load_script

vl = load_module("vaultlib")
ns = load_script("night-shift.py")

NOW = dt.datetime(2024, 5, 8, 9, 30, tzinfo=dt.timezone.utc)  # 04:30 in the default time zone
YESTERDAY = (NOW.astimezone(vl.TZ).date() - dt.timedelta(days=1)).isoformat()
DAY = {"new": 40, "kept_score": 9, "kept_watchlist": 1, "read_low_score": 24, "read_duplicate": 4,
       "read_non_english": 2}


def hours_ago(h):
    return NOW - dt.timedelta(hours=h)


class Vault(unittest.TestCase):
    """A throwaway vault folder, with helpers that write the files the other jobs leave."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)

    def write(self, rel, text, age_h=None):
        path = self.vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if age_h is not None:
            t = hours_ago(age_h).timestamp()
            os.utime(path, (t, t))
        return path

    def sorter_state(self, last_run_h=0.5, days=None):
        self.write(ns.SORTER_STATE, json.dumps({
            "last_id": 1234, "last_run": hours_ago(last_run_h).isoformat(),
            "days": {YESTERDAY: DAY} if days is None else days}))

    def article(self, name, created_h, processed=False, kind="article"):
        fm = ["---", f"created: {hours_ago(created_h).astimezone(vl.TZ).isoformat()}", f"type: {kind}",
              "status: inbox", "tags: [reading]"] + (["processed: 2024-05-08"] if processed else [])
        self.write(f"{ns.READING_DIR}/{name}.md", "\n".join(fm + ["---", "", f"# {name}", ""]))

    def export(self, age_h=3):
        for rel in ns.EXPORT_FILES:
            self.write(rel, "{}\n", age_h=age_h)

    def healthy(self):
        self.sorter_state()
        self.article("First article", 30, processed=True)
        self.article("Second article", 5, processed=True)
        self.article("Third article", 1)
        self.export()
        self.write(ns.SORTER_REVIEW, "# Feed Sorter Review\n")

    def health(self):
        return ns.pipeline_health(str(self.vault), NOW)


class PipelineHealth(Vault):
    def test_healthy_is_one_quiet_line_plus_the_counts(self):
        self.healthy()
        lines, warnings = self.health()
        self.assertEqual(warnings, [])
        self.assertEqual(lines, [
            "- All well: the feed sorter, the reading inbox and the Miniflux export are keeping up.",
            "- Feed sorter: yesterday 40 new, 10 left unread, 30 marked read.",
            "- Reading inbox: 2 added in the last 24 h, 1 of them processed; 1 waiting.",
            "- Details: [[Agents/Generated/Feed Health|Feed Health]], "
            "[[Agents/Generated/Feed Sorter Review|Feed Sorter Review]]"])

    def test_empty_vault_degrades_to_no_data_lines(self):
        lines, warnings = self.health()
        self.assertEqual(lines[-2:], ["- Feed sorter: no data (state file missing).",
                                      "- Reading inbox: no data (no Inbox/Reading folder)."])
        self.assertEqual(len(warnings), 2)  # the sorter's state and the configuration copy
        self.assertIn("feed-sorter-state.json is missing", warnings[0])
        self.assertIn("miniflux-config.json is missing", warnings[1])
        self.assertEqual(lines[:2], [f"- **Warning:** {w}" for w in warnings])

    def test_vault_folder_that_does_not_exist(self):
        lines, warnings = ns.pipeline_health(str(self.vault / "nowhere"), NOW)
        self.assertTrue(lines and warnings)

    def test_stale_sorter(self):
        self.healthy()
        self.sorter_state(last_run_h=7)
        lines, warnings = self.health()
        self.assertEqual(len(warnings), 1)
        self.assertRegex(warnings[0], r"^Feed sorter: has handled no new entry for 7 h \(last: \w{3} \d\d:\d\d\)")
        self.assertEqual(lines[0], f"- **Warning:** {warnings[0]}")
        self.assertIn("- Feed sorter: yesterday 40 new, 10 left unread, 30 marked read.", lines)

    def test_sorter_just_inside_the_limit_is_fine(self):
        self.healthy()
        self.sorter_state(last_run_h=2.9)
        self.assertEqual(self.health()[1], [])

    def test_sorter_state_without_yesterday_or_last_run(self):
        self.healthy()
        self.write(ns.SORTER_STATE, json.dumps({"last_id": 5, "days": {"2001-01-01": DAY}}))
        lines, warnings = self.health()
        self.assertIn(f"- Feed sorter: no counts for yesterday ({YESTERDAY}).", lines)
        self.assertEqual(warnings, ["Feed sorter: the state file records no last run."])

    def test_malformed_json_everywhere(self):
        self.healthy()
        self.write(ns.SORTER_STATE, "{not json")
        self.write(ns.READING_TRIES, "[1, 2")
        self.write(ns.EXPORT_FILES[0], "\x00garbage", age_h=1)
        lines, warnings = self.health()
        self.assertIn("- Feed sorter: no data (state file unreadable).", lines)
        self.assertEqual(len(warnings), 1)
        self.assertIn("feed-sorter-state.json is unreadable", warnings[0])
        self.assertIn("- Reading inbox: 2 added in the last 24 h, 1 of them processed; 1 waiting.", lines)

    def test_wrong_shapes_in_the_state_file(self):
        self.healthy()
        for state in ("[]", '"text"', "", '{"days": [], "last_run": 5}', '{"days": {"%s": 3}, "last_run": "soon"}' % YESTERDAY,
                      '{"days": {"%s": {"new": "many", "kept_score": null, "read_x": -4}}, "last_run": "2024-05-08"}' % YESTERDAY):
            with self.subTest(state=state):
                self.write(ns.SORTER_STATE, state)
                lines, warnings = self.health()
                self.assertTrue(any(line.startswith("- Feed sorter: ") for line in lines))
                self.assertEqual(len(warnings), 1)

    def test_last_run_without_a_time_zone_is_read_as_utc(self):
        self.healthy()
        self.write(ns.SORTER_STATE, json.dumps({"last_run": hours_ago(1).replace(tzinfo=None).isoformat(), "days": {}}))
        self.assertEqual(self.health()[1], [])

    def test_waiting_articles(self):
        self.healthy()
        self.article("Fourth article", 9)
        self.article("Fifth article", 4)
        lines, warnings = self.health()
        self.assertIn("- Reading inbox: 4 added in the last 24 h, 1 of them processed; 3 waiting.", lines)
        self.assertEqual(warnings, ["Reading inbox: 2 article(s) waiting more than 3 h to be processed "
                                    "(oldest 9 h: [[Fourth article]])."])

    def test_attempt_limit(self):
        self.healthy()
        self.article("Broken page", 50)
        self.article("Second try", 2)
        self.write(ns.READING_TRIES, json.dumps({"Broken page.md": 3, "Second try.md": 2, "Gone.md": 3}))
        lines, warnings = self.health()
        self.assertIn("- Reading inbox: 3 added in the last 24 h, 1 of them processed; 2 waiting, 1 given up.", lines)
        self.assertEqual(warnings, ["Reading inbox: 1 article(s) given up after 3 failed attempts (e.g. [[Broken page]])."])

    def test_only_article_notes_count(self):
        self.healthy()
        self.article("A filed index", 9, kind="index")
        self.write(f"{ns.READING_DIR}/No frontmatter.md", "Just text.\n", age_h=9)
        self.write(f"{ns.READING_DIR}/ledger.json", "{}", age_h=9)
        (self.vault / ns.READING_DIR / "Odd.md").mkdir()
        self.assertEqual(self.health()[1], [])

    def test_article_without_a_usable_created_uses_the_file_time(self):
        self.healthy()
        self.write(f"{ns.READING_DIR}/Old style.md", "---\ncreated: 2024-05-01\ntype: article\n---\n", age_h=6)
        _, warnings = self.health()
        self.assertEqual(warnings, ["Reading inbox: 1 article(s) waiting more than 3 h to be processed "
                                    "(oldest 6 h: [[Old style]])."])

    def test_export_missing(self):
        self.healthy()
        (self.vault / ns.EXPORT_FILES[0]).unlink()
        _, warnings = self.health()
        self.assertEqual(len(warnings), 1)
        self.assertIn("miniflux-config.json is missing", warnings[0])

    def test_export_stale(self):
        self.healthy()
        self.export(age_h=60)
        lines, warnings = self.health()
        self.assertEqual(warnings, ["Miniflux export: nothing written for 2 d; it runs every night."])
        self.assertIn("- Details: [[Agents/Generated/Feed Health|Feed Health]], "
                      "[[Agents/Generated/Feed Sorter Review|Feed Sorter Review]]", lines)

    def test_unchanged_configuration_is_not_stale_while_another_export_file_is_fresh(self):
        # miniflux-export.py rewrites a file only when its content changed.
        self.healthy()
        self.export(age_h=200)
        self.write(ns.FEED_HEALTH, "# Feed Health\n", age_h=3)
        self.assertEqual(self.health()[1], [])

    def test_no_links_to_notes_that_do_not_exist(self):
        self.sorter_state()
        self.write(ns.EXPORT_FILES[0], "{}\n", age_h=3)
        lines, _ = self.health()
        self.assertFalse([line for line in lines if line.startswith("- Details")])

    def test_never_raises(self):
        def boom(*_):
            raise RuntimeError("disk on fire")
        original, ns.sorter_health = ns.sorter_health, boom
        self.addCleanup(setattr, ns, "sorter_health", original)
        self.assertEqual(self.health(), (["- No data: the pipeline health check failed (RuntimeError)."], []))

    def test_every_warning_fits_the_problems_section(self):
        # main() cuts a problem at 300 characters; a cut wikilink would be a broken link.
        self.sorter_state(last_run_h=99)
        self.article("x" * 101, 90)   # reading-inbox.py keeps names to about 100 characters
        self.article("y" * 101, 80)
        self.write(ns.READING_TRIES, json.dumps({"y" * 101 + ".md": 3}))
        _, warnings = self.health()
        self.assertEqual(len(warnings), 4)
        self.assertLess(max(map(len, warnings)), 300)


NOTE = """---
type: reference
---

# Feed Interests

## Interests

- a made-up interest

## Priority categories

Read first, every morning.

- Example category
* "Another `one`"
-   example CATEGORY
- (replace me) a category name
- [[Linked name]]

## Watchlist

- Example name
"""


class PriorityCategories(Vault):
    def test_names_in_the_owners_order_without_repeats_or_placeholders(self):
        self.write(ns.PROFILE_NOTE, NOTE)
        self.assertEqual(ns.priority_categories(str(self.vault)), ["Example category", "Another one", "Linked name"])

    def test_missing_note_or_section(self):
        self.assertEqual(ns.priority_categories(str(self.vault)), [])
        self.write(ns.PROFILE_NOTE, "## Interests\n\n- another made-up interest\n")
        self.assertEqual(ns.priority_categories(str(self.vault)), [])
        self.write(ns.PROFILE_NOTE, "## Priority categories\n\nNone yet.\n")
        self.assertEqual(ns.priority_categories(str(self.vault)), [])

    def test_unreadable_note(self):
        (self.vault / ns.PROFILE_NOTE).mkdir(parents=True)
        self.assertEqual(ns.priority_categories(str(self.vault)), [])
        (self.vault / ns.PROFILE_NOTE).rmdir()
        (self.vault / ns.PROFILE_NOTE).write_bytes(b"## Priority categories\n- \xff\xfe\n")
        self.assertEqual(ns.priority_categories(str(self.vault)), [])

    def test_heading_case_and_a_cap_on_the_list(self):
        self.write(ns.PROFILE_NOTE, "## PRIORITY Categories\n" + "".join(f"- Category {i}\n" for i in range(30)))
        names = ns.priority_categories(str(self.vault))
        self.assertEqual(len(names), ns.PRIORITY_MAX)
        self.assertEqual(names[0], "Category 0")

    def test_a_name_is_one_short_line_that_cannot_close_its_quotes(self):
        self.assertEqual(ns.category_name('  A "quoted"\tname  '), "A quoted name")
        self.assertEqual(len(ns.category_name("x" * 200)), 60)
        self.assertEqual(ns.category_name(None), "")


class FeedsRequest(unittest.TestCase):
    SINCE = NOW - dt.timedelta(hours=24)
    FORMAT = 'Reply with only a JSON object: {"items": [{"category": '

    def request(self, **kw):
        return ns.feeds_request(NOW, self.SINCE, "all", **kw)

    def test_without_priorities_or_a_sorted_category_it_is_the_plain_request(self):
        text = self.request()
        self.assertTrue(text.startswith(
            "Feeds digest for my morning brief. Now: 2024-05-08 09:30 UTC. Since: 2024-05-07 09:30 UTC "
            f"(published_after={int(self.SINCE.timestamp())}). Categories: all.\n"
            "Read the entries published since then and pick at most 12 worth my time, most important first.\n"
            + self.FORMAT))
        self.assertNotIn("Priority", text)
        self.assertNotIn("unread", text)
        self.assertTrue(text.endswith("Never invent items."))

    def test_priority_categories_are_named_in_order_before_the_output_format(self):
        text = self.request(priority=["Example category", "Another one"])
        self.assertIn('Priority categories: "Example category", "Another one". Read these before any other', text)
        self.assertIn("read them completely", text)
        self.assertIn('first in "items"', text)
        self.assertLess(text.index("Priority categories"), text.index(self.FORMAT))
        self.assertNotIn("status=unread", text)

    def test_sorted_category_is_limited_to_unread_entries_and_stays_read_only(self):
        text = self.request(sorted_category="Example firehose")
        self.assertIn('Pre-sorted category: "Example firehose".', text)
        self.assertIn("status=unread", text)
        self.assertIn("keep published_after", text)
        self.assertIn("never change the status of an entry", text)
        self.assertNotIn("Priority categories", text)

    def test_both_rules_and_the_limits(self):
        text = ns.feeds_request(NOW, self.SINCE, "Category A, Category B", ["Example category"], "Example firehose", 5)
        self.assertIn("Categories: Category A, Category B.", text)
        self.assertIn("pick at most 5 worth", text)
        self.assertLess(text.index("Priority categories"), text.index("Pre-sorted category"))
        self.assertEqual(text.count(self.FORMAT), 1)
        for key in ('"items"', '"category"', '"title"', '"feed"', '"url"', '"why"', '"notes"', '"errors"'):
            self.assertIn(key, text)

    def test_the_default_sorted_category(self):
        self.assertEqual(ns.SORTED_CATEGORY, "Security firehose")  # feed-sorter.py's SORT_CATEGORY default


class PriorityFirst(unittest.TestCase):
    ROWS = [{"category": "Category A", "title": "a"}, {"category": "Another one", "title": "b"},
            {"category": " example  CATEGORY ", "title": "c"}, {"category": "Category A", "title": "d"},
            {"title": "e"}, {"category": "Another one", "title": "f"}, {"category": None, "title": "g"}]

    def test_priority_items_first_in_the_owners_order_and_the_rest_as_given(self):
        rows = ns.priority_first(self.ROWS, ["Example category", "Another one"])
        self.assertEqual("".join(r["title"] for r in rows), "cbfadeg")

    def test_no_priorities_changes_nothing(self):
        self.assertEqual(ns.priority_first(self.ROWS, []), self.ROWS)


class ReplyStillParses(unittest.TestCase):
    def test_the_answer_shape_the_request_asks_for(self):
        data, rows = ns.reply_items('Done.\n{"items": [{"category": "Example category", "title": "T", '
                                    '"feed": "F", "url": "https://example.com/a", "why": "w"}], '
                                    '"notes": "Category A: read 40 of 95", "errors": []}')
        self.assertEqual(len(rows), 1)
        self.assertEqual(ns.reply_notes("", data, "notes", 1), ["Category A: read 40 of 95"])


if __name__ == "__main__":
    unittest.main()

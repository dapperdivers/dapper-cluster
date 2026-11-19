import os
import tempfile
import unittest

from helpers import load_module

librarian = load_module("librarian")

TRANSCRIPT = ("So I think the raised beds should go on the south side of the garden this year. "
              "Yes. Also remember to order compost before the end of the month.")
FOLDERS = ["Projects", "Projects/Garden", "Library"]


class Validate(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.vault = tmp.name
        for rel in ("Projects/Garden/Raised beds.md", "Projects/Garden/Compost.md", "Inbox/Loose idea.md",
                    "Projects/Garden/plan.pdf", "Top secret.md"):
            path = os.path.join(self.vault, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# note\n")

    def validate(self, raw):
        return librarian.validate(self.vault, raw, TRANSCRIPT, FOLDERS)

    def test_related_keeps_only_notes_that_exist_outside_the_inbox(self):
        out = self.validate({"related": [
            "Projects/Garden/Raised beds.md",
            "Projects/Garden/Missing.md",       # not in the vault
            "Inbox/Loose idea.md",              # exists, but under Inbox/
            "Projects/Garden/plan.pdf",         # exists, but not a note
            "Projects/Garden",                  # a folder
            "Projects/../Top secret.md",        # path traversal
            " /Projects/Garden/Compost.md ",    # tidied, then kept
            "Projects/Garden/Raised beds.md",   # repeat
            42, None,
        ]})
        self.assertEqual(out["related"], ["Projects/Garden/Raised beds.md", "Projects/Garden/Compost.md"])

    def test_related_is_capped_at_five(self):
        for i in range(8):
            with open(os.path.join(self.vault, f"Projects/n{i}.md"), "w", encoding="utf-8") as fh:
                fh.write("x\n")
        out = self.validate({"related": [f"Projects/n{i}.md" for i in range(8)]})
        self.assertEqual(out["related"], [f"Projects/n{i}.md" for i in range(5)])

    def test_folder_from_the_candidates_is_kept(self):
        self.assertEqual(self.validate({"folder": "Projects/Garden"})["folder"], "Projects/Garden")
        self.assertEqual(self.validate({"folder": " /Projects/Garden/ "})["folder"], "Projects/Garden")

    def test_folder_not_in_the_candidates_is_dropped(self):
        for folder in ("Projects/Kitchen", "Inbox", "projects/garden", "", None, 7, ["Projects"]):
            with self.subTest(folder=folder):
                self.assertEqual(self.validate({"folder": folder})["folder"], "")

    def test_answer_must_be_an_object(self):
        for raw in (None, [], "Projects/Garden"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.validate(raw)

    def test_empty_answer(self):
        self.assertEqual(self.validate({}), {"folder": "", "related": [], "zettels": [], "dropped": 0})

    def test_wrong_types_are_treated_as_empty(self):
        out = self.validate({"related": "Projects/Garden/Compost.md", "zettels": {"title": "x"}})
        self.assertEqual((out["related"], out["zettels"]), ([], []))

    def test_zettel_take_must_be_in_the_transcript(self):
        good = {"title": "Beds: south side?", "claim": "Raised beds belong on the south side.",
                "take": '"The raised beds should go on the SOUTH side of the garden this year."',
                "confidence": "certain", "domain": "Garden!", "tags": ["#Garden", "not a tag", "beds"]}
        out = self.validate({"zettels": [
            good,
            dict(good, title="Invented", take="Raised beds are a waste of money and effort overall."),
            dict(good, title="Too short", take="Yes."),
        ]})
        self.assertEqual(out["dropped"], 2)
        self.assertEqual(len(out["zettels"]), 1)
        z = out["zettels"][0]
        self.assertEqual(z["title"], "Beds south side")
        self.assertEqual(z["take"], "The raised beds should go on the SOUTH side of the garden this year.")
        self.assertEqual((z["confidence"], z["domain"], z["tags"]), ("medium", "garden", ["garden", "beds"]))


if __name__ == "__main__":
    unittest.main()

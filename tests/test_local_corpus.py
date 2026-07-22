from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_corpus import LocalCorpus


class LocalCorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.corpus = LocalCorpus.from_file(Path(__file__).resolve().parents[1] / "data" / "corpus.json")

    def test_recorded_variant_resolves_to_canonical_entry(self) -> None:
        results = self.corpus.search("孝子")
        self.assertTrue(any(item["term"] == "孝" for item in results))

    def test_read_and_activate_are_snapshot_local(self) -> None:
        card = self.corpus.search("孝")[0]
        self.assertEqual(self.corpus.read(card["id"])["id"], card["id"])
        activated = self.corpus.activate("有人无脑维护主播", ["孝子"])
        self.assertTrue(activated["activations"])


if __name__ == "__main__":
    unittest.main()

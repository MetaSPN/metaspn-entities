import tempfile
import unittest
from pathlib import Path

from metaspn_entities.resolver import EntityResolver
from metaspn_entities.sqlite_backend import SQLiteEntityStore


class AttributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_merge_after_attempt_before_outcome(self) -> None:
        attempt = self.resolver.resolve("twitter_handle", "attempt_user")
        winner = self.resolver.resolve("twitter_handle", "winner_user")
        self.resolver.add_alias(attempt.entity_id, "email", "attempt@example.com", confidence=0.9)

        # Merge happens between attempt capture and outcome ingestion.
        self.resolver.merge_entities(attempt.entity_id, winner.entity_id, reason="dedupe")

        result = self.resolver.attribute_outcome(
            {
                "entity_id": attempt.entity_id,
                "email": "attempt@example.com",
            }
        )
        self.assertEqual(result.entity_id, winner.entity_id)
        self.assertGreater(result.confidence, 0.9)

    def test_undo_merge_edge_case(self) -> None:
        a = self.resolver.resolve("twitter_handle", "undo_attr_a")
        b = self.resolver.resolve("twitter_handle", "undo_attr_b")
        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="dedupe")
        self.resolver.undo_merge(a.entity_id, b.entity_id)

        # After undo implementation, b redirects to a.
        result = self.resolver.attribute_outcome({"entity_id": b.entity_id})
        self.assertEqual(result.entity_id, a.entity_id)
        self.assertAlmostEqual(result.confidence, 0.99, places=6)

    def test_conflicting_aliases_tie_break_by_confidence(self) -> None:
        high = self.resolver.resolve("twitter_handle", "high_conf")
        low = self.resolver.resolve("twitter_handle", "low_conf")

        self.resolver.add_alias(high.entity_id, "email", "high@example.com", confidence=0.95)
        self.resolver.add_alias(low.entity_id, "canonical_url", "https://low.example.com/profile", confidence=0.60)

        result = self.resolver.attribute_outcome(
            {
                "email": "HIGH@example.com",
                "canonical_url": "https://low.example.com/profile/",
            }
        )
        self.assertEqual(result.entity_id, high.entity_id)
        self.assertAlmostEqual(result.confidence, 0.475, places=6)


if __name__ == "__main__":
    unittest.main()

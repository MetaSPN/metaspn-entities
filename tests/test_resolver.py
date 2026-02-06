import tempfile
import unittest
from pathlib import Path

from metaspn_entities import EntityResolver, SQLiteEntityStore


class ResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_exact_match_resolution(self) -> None:
        first = self.resolver.resolve("twitter_handle", "@same")
        second = self.resolver.resolve("twitter_handle", "same")
        self.assertEqual(first.entity_id, second.entity_id)
        self.assertFalse(second.created_new_entity)

    def test_alias_addition(self) -> None:
        created = self.resolver.resolve("twitter_handle", "alpha")
        events = self.resolver.add_alias(created.entity_id, "email", "alpha@example.com", caused_by="manual")
        self.assertEqual(len(events), 1)

        again = self.resolver.resolve("email", "ALPHA@example.com")
        self.assertEqual(again.entity_id, created.entity_id)

    def test_merge_correctness(self) -> None:
        a = self.resolver.resolve("twitter_handle", "person_a")
        b = self.resolver.resolve("twitter_handle", "person_b")
        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="manual dedupe", caused_by="reviewer")

        merged = self.resolver.resolve("twitter_handle", "person_a")
        self.assertEqual(merged.entity_id, b.entity_id)

    def test_merge_history(self) -> None:
        a = self.resolver.resolve("twitter_handle", "x_a")
        b = self.resolver.resolve("twitter_handle", "x_b")
        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="dedupe", caused_by="reviewer")
        history = self.resolver.merge_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["from_entity_id"], a.entity_id)
        self.assertEqual(history[0]["to_entity_id"], b.entity_id)

    def test_merge_undo_via_reverse_merge(self) -> None:
        a = self.resolver.resolve("twitter_handle", "undo_a")
        b = self.resolver.resolve("twitter_handle", "undo_b")
        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="dedupe", caused_by="reviewer")
        merged = self.resolver.resolve("twitter_handle", "undo_a")
        self.assertEqual(merged.entity_id, b.entity_id)
        self.resolver.undo_merge(a.entity_id, b.entity_id, caused_by="reviewer")

        current_a = self.resolver.resolve("twitter_handle", "undo_a")
        current_b = self.resolver.resolve("twitter_handle", "undo_b")
        self.assertEqual(current_a.entity_id, a.entity_id)
        self.assertEqual(current_b.entity_id, a.entity_id)

    def test_confidence_behavior(self) -> None:
        first = self.resolver.resolve("email", "test@example.com", context={"confidence": 0.7})
        second = self.resolver.resolve("email", "test@example.com", context={"confidence": 0.4})
        self.assertEqual(first.entity_id, second.entity_id)
        self.assertGreaterEqual(second.confidence, 0.7)

    def test_auto_merge_on_email(self) -> None:
        a = self.resolver.resolve("twitter_handle", "owner_a")
        b = self.resolver.resolve("twitter_handle", "owner_b")

        self.resolver.add_alias(a.entity_id, "email", "shared@example.com")
        events = self.resolver.add_alias(b.entity_id, "email", "shared@example.com")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "EntityMerged")

        # resolving either alias should route to same canonical entity
        one = self.resolver.resolve("twitter_handle", "owner_a")
        two = self.resolver.resolve("twitter_handle", "owner_b")
        self.assertEqual(one.entity_id, two.entity_id)
        shared = self.resolver.resolve("email", "shared@example.com")
        self.assertEqual(one.entity_id, shared.entity_id)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from metaspn_entities import SQLiteEntityStore
from metaspn_entities.adapter import resolve_normalized_social_signal
from metaspn_entities.resolver import EntityResolver


class ContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_cross_platform_handle_normalization_in_context(self) -> None:
        twitter = {
            "source": "social.ingest",
            "payload": {
                "platform": "twitter",
                "author_handle": "Alice_One",
                "profile_url": "https://example.com/u/alice",
            },
        }
        linkedin = {
            "source": "social.ingest",
            "payload": {
                "platform": "linkedin",
                "handle": "alice-one",
                "profile_url": "http://www.example.com/u/alice/",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, twitter)
        second = resolve_normalized_social_signal(self.resolver, linkedin)
        self.assertEqual(first.entity_id, second.entity_id)

        context = self.resolver.entity_context(first.entity_id)
        identifier_types = {item["identifier_type"] for item in context.identifiers}
        self.assertIn("twitter_handle", identifier_types)
        self.assertIn("linkedin_handle", identifier_types)
        self.assertIn("canonical_url", identifier_types)

    def test_merged_entity_context_continuity(self) -> None:
        a = self.resolver.resolve("twitter_handle", "merge_ctx_a")
        b = self.resolver.resolve("twitter_handle", "merge_ctx_b")
        self.resolver.add_alias(a.entity_id, "email", "a@example.com", caused_by="manual")
        self.resolver.add_alias(b.entity_id, "domain", "example.com", caused_by="manual")
        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="dedupe", caused_by="manual")

        context_from = self.resolver.entity_context(a.entity_id)
        context_to = self.resolver.entity_context(b.entity_id)

        self.assertEqual(context_from.entity_id, context_to.entity_id)
        normalized_values = {item["normalized_value"] for item in context_from.aliases}
        self.assertIn("merge_ctx_a", normalized_values)
        self.assertIn("merge_ctx_b", normalized_values)

    def test_rerun_stability_for_context_and_confidence(self) -> None:
        signal = {
            "source": "social.ingest",
            "payload": {
                "platform": "twitter",
                "author_handle": "stable_ctx",
                "profile_url": "https://example.org/stable_ctx",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, signal)
        context_1 = self.resolver.entity_context(first.entity_id)
        summary_1 = self.resolver.confidence_summary(first.entity_id)

        second = resolve_normalized_social_signal(self.resolver, signal)
        context_2 = self.resolver.entity_context(second.entity_id)
        summary_2 = self.resolver.confidence_summary(second.entity_id)

        self.assertEqual(first.entity_id, second.entity_id)
        self.assertEqual(context_1.entity_id, context_2.entity_id)
        self.assertEqual(context_1.aliases, context_2.aliases)
        self.assertEqual(context_1.identifiers, context_2.identifiers)
        self.assertEqual(summary_1, summary_2)


if __name__ == "__main__":
    unittest.main()

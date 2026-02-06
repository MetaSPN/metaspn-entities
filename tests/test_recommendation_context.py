import tempfile
import unittest
from pathlib import Path

from metaspn_entities.adapter import resolve_normalized_social_signal
from metaspn_entities.resolver import EntityResolver
from metaspn_entities.sqlite_backend import SQLiteEntityStore


class RecommendationContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_cross_source_consistency(self) -> None:
        signal_a = {
            "source": "social.ingest.twitter",
            "payload": {
                "platform": "twitter",
                "author_handle": "rec_user",
                "profile_url": "https://example.com/p/rec_user",
            },
        }
        signal_b = {
            "source": "social.ingest.linkedin",
            "payload": {
                "platform": "linkedin",
                "handle": "rec-user",
                "profile_url": "http://www.example.com/p/rec_user/",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, signal_a)
        second = resolve_normalized_social_signal(self.resolver, signal_b)
        self.assertEqual(first.entity_id, second.entity_id)

        rec = self.resolver.recommendation_context(first.entity_id)
        self.assertEqual(rec.entity_id, first.entity_id)
        self.assertGreaterEqual(rec.identity_confidence, 0.0)
        self.assertIn(rec.relationship_stage_hint, {"cold", "warm", "engaged"})
        self.assertIn("social.ingest.linkedin", rec.interaction_history_summary["sources"])
        self.assertIn("social.ingest.twitter", rec.interaction_history_summary["sources"])

    def test_merge_safe_continuity(self) -> None:
        a = self.resolver.resolve("twitter_handle", "merge_rec_a")
        b = self.resolver.resolve("twitter_handle", "merge_rec_b")
        self.resolver.add_alias(a.entity_id, "email", "a@rec.dev")
        self.resolver.add_alias(b.entity_id, "domain", "rec.dev")
        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="dedupe")

        rec_from = self.resolver.recommendation_context(a.entity_id)
        rec_to = self.resolver.recommendation_context(b.entity_id)

        self.assertEqual(rec_from.entity_id, rec_to.entity_id)
        self.assertEqual(rec_from.continuity["canonical_entity_id"], rec_to.continuity["canonical_entity_id"])
        self.assertGreaterEqual(rec_from.continuity["identifier_count"], 2)

    def test_rerun_determinism(self) -> None:
        signal = {
            "source": "social.ingest",
            "payload": {
                "platform": "twitter",
                "author_handle": "deterministic_rec",
                "profile_url": "https://example.org/deterministic_rec",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, signal)
        rec_1 = self.resolver.recommendation_context(first.entity_id)

        second = resolve_normalized_social_signal(self.resolver, signal)
        rec_2 = self.resolver.recommendation_context(second.entity_id)

        self.assertEqual(first.entity_id, second.entity_id)
        self.assertEqual(rec_1.entity_id, rec_2.entity_id)
        self.assertEqual(rec_1.preferred_channel_hint, rec_2.preferred_channel_hint)
        self.assertEqual(rec_1.relationship_stage_hint, rec_2.relationship_stage_hint)
        self.assertEqual(rec_1.continuity, rec_2.continuity)
        self.assertEqual(rec_1.interaction_history_summary, rec_2.interaction_history_summary)


if __name__ == "__main__":
    unittest.main()

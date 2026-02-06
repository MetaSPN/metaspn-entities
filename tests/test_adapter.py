import importlib
import sys
import tempfile
import unittest
from pathlib import Path

from metaspn_entities import SQLiteEntityStore
from metaspn_entities.adapter import resolve_normalized_social_signal
from metaspn_entities.resolver import EntityResolver


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_same_author_over_multiple_posts(self) -> None:
        first_signal = {
            "source": "social.ingest",
            "payload_type": "SocialPostSeen",
            "payload": {
                "platform": "twitter",
                "post_id": "p1",
                "author_handle": "@same_author",
                "url": "https://x.com/same_author/status/1",
            },
        }
        second_signal = {
            "source": "social.ingest",
            "payload_type": "SocialPostSeen",
            "payload": {
                "platform": "twitter",
                "post_id": "p2",
                "author_handle": "same_author",
                "url": "https://x.com/same_author/status/2",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, first_signal)
        second = resolve_normalized_social_signal(self.resolver, second_signal)

        self.assertEqual(first.entity_id, second.entity_id)

    def test_cross_platform_identifier_normalization(self) -> None:
        twitter_signal = {
            "source": "social.ingest",
            "payload_type": "SocialPostSeen",
            "payload": {
                "platform": "twitter",
                "post_id": "p100",
                "author_handle": "alice",
                "profile_url": "https://example.com/team/alice/",
            },
        }
        linkedin_signal = {
            "source": "social.ingest",
            "payload_type": "ProfileSnapshotSeen",
            "payload": {
                "platform": "linkedin",
                "profile_id": "li-77",
                "handle": "alice-smith",
                "profile_url": "http://www.example.com/team/alice",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, twitter_signal)
        second = resolve_normalized_social_signal(self.resolver, linkedin_signal)

        self.assertEqual(first.entity_id, second.entity_id)

    def test_idempotent_rerun_behavior(self) -> None:
        signal = {
            "source": "social.ingest",
            "payload_type": "SocialPostSeen",
            "payload": {
                "platform": "twitter",
                "post_id": "idempotent-1",
                "author_handle": "rerun_author",
                "profile_url": "https://example.org/rerun_author",
            },
        }

        first = resolve_normalized_social_signal(self.resolver, signal)
        second = resolve_normalized_social_signal(self.resolver, signal)

        self.assertEqual(first.entity_id, second.entity_id)
        self.assertEqual(
            [event.event_type for event in second.emitted_events],
            ["EntityResolved"],
        )

    def test_emitted_events_parse_with_metaspn_schemas(self) -> None:
        entities_module = None
        try:
            entities_module = importlib.import_module("metaspn_schemas.entities")
        except Exception:
            sibling_src = Path(__file__).resolve().parents[2] / "metaspn-schemas" / "src"
            if sibling_src.exists():
                sys.path.insert(0, str(sibling_src))
                entities_module = importlib.import_module("metaspn_schemas.entities")

        if entities_module is None:
            self.skipTest("metaspn_schemas is unavailable")

        signal = {
            "source": "social.ingest",
            "payload_type": "SocialPostSeen",
            "payload": {
                "platform": "twitter",
                "post_id": "schema-1",
                "author_handle": "schema_user",
                "profile_url": "https://example.net/schema_user",
            },
        }

        result = resolve_normalized_social_signal(self.resolver, signal)
        for event in result.emitted_events:
            if event.event_type == "EntityResolved":
                parsed = entities_module.EntityResolved.from_dict(event.payload)
                self.assertEqual(parsed.entity_id, result.entity_id)
            elif event.event_type == "EntityAliasAdded":
                parsed = entities_module.EntityAliasAdded.from_dict(event.payload)
                self.assertTrue(parsed.alias)
            elif event.event_type == "EntityMerged":
                parsed = entities_module.EntityMerged.from_dict(event.payload)
                self.assertTrue(parsed.merged_from)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from metaspn_entities.demo import resolve_demo_social_identity
from metaspn_entities.resolver import EntityResolver
from metaspn_entities.sqlite_backend import SQLiteEntityStore


class DemoSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_same_author_repeated_days_stable_entity(self) -> None:
        day_1 = {
            "platform": "x",
            "author_handle": "@DemoAuthor",
            "profile_url": "https://x.com/demoauthor",
            "source": "demo.day1",
        }
        day_2 = {
            "platform": "x",
            "author_handle": "demoauthor",
            "profile_url": "https://x.com/demoauthor/",
            "source": "demo.day2",
        }

        first = resolve_demo_social_identity(self.resolver, day_1)
        second = resolve_demo_social_identity(self.resolver, day_2)

        self.assertEqual(first["entity_id"], second["entity_id"])

    def test_alias_collision_merge_safe_continuity(self) -> None:
        one = resolve_demo_social_identity(
            self.resolver,
            {
                "platform": "twitter",
                "author_handle": "alpha_demo",
                "profile_url": "https://example.com/u/shared",
                "source": "demo.a",
            },
        )
        two = resolve_demo_social_identity(
            self.resolver,
            {
                "platform": "linkedin",
                "author_handle": "beta_demo",
                "profile_url": "http://www.example.com/u/shared/",
                "source": "demo.b",
            },
        )

        # canonical_url collision should keep one canonical identity for both reruns.
        self.assertEqual(one["entity_id"], two["entity_id"])

    def test_digest_payload_contains_explainability_context(self) -> None:
        payload = resolve_demo_social_identity(
            self.resolver,
            {
                "platform": "bluesky",
                "author_handle": "DigestUser",
                "profile_url": "https://bsky.app/profile/digestuser",
                "source": "demo.digest",
            },
        )

        self.assertIn("entity_id", payload)
        self.assertIn("confidence", payload)
        self.assertIn("matched_identifiers", payload)
        self.assertIn("why", payload)
        self.assertIn("confidence_summary", payload["why"])
        self.assertGreaterEqual(payload["why"]["matched_identifier_count"], 1)
        self.assertIsInstance(payload["events"], list)


if __name__ == "__main__":
    unittest.main()

import importlib
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from metaspn_entities import EntityResolver, SQLiteEntityStore


class EventContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_entity_resolved_payload_shape(self) -> None:
        self.resolver.resolve("twitter_handle", "contract_user")
        event = self.resolver.drain_events()[-1]

        self.assertEqual(event.event_type, "EntityResolved")
        self.assertEqual(
            sorted(event.payload.keys()),
            ["confidence", "entity_id", "resolved_at", "resolver", "schema_version"],
        )
        self.assertIsInstance(event.payload["resolver"], str)
        self.assertGreaterEqual(float(event.payload["confidence"]), 0.0)
        datetime.fromisoformat(event.payload["resolved_at"])

    def test_entity_merged_payload_shape(self) -> None:
        a = self.resolver.resolve("twitter_handle", "merge_a")
        b = self.resolver.resolve("twitter_handle", "merge_b")
        self.resolver.drain_events()

        self.resolver.merge_entities(a.entity_id, b.entity_id, reason="dedupe")
        event = self.resolver.drain_events()[-1]

        self.assertEqual(event.event_type, "EntityMerged")
        self.assertEqual(
            sorted(event.payload.keys()),
            ["entity_id", "merged_at", "merged_from", "reason", "schema_version"],
        )
        self.assertEqual(event.payload["entity_id"], b.entity_id)
        self.assertEqual(event.payload["merged_from"], [a.entity_id])
        datetime.fromisoformat(event.payload["merged_at"])

    def test_entity_alias_added_payload_shape(self) -> None:
        created = self.resolver.resolve("twitter_handle", "alias_contract")
        self.resolver.drain_events()

        events = self.resolver.add_alias(created.entity_id, "email", "alias@example.com")
        self.assertEqual(len(events), 1)
        event = events[0]

        self.assertEqual(event.event_type, "EntityAliasAdded")
        self.assertEqual(
            sorted(event.payload.keys()),
            ["added_at", "alias", "alias_type", "entity_id", "schema_version"],
        )
        self.assertEqual(event.payload["entity_id"], created.entity_id)
        self.assertEqual(event.payload["alias_type"], "email")
        self.assertEqual(event.payload["alias"], "alias@example.com")
        datetime.fromisoformat(event.payload["added_at"])

    def test_schema_round_trip_when_metaspn_schemas_is_available(self) -> None:
        # Try import from installed package first, then from sibling checkout if present.
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

        self.resolver.resolve("twitter_handle", "roundtrip_user")
        resolved_event = self.resolver.drain_events()[-1]

        entity_resolved = entities_module.EntityResolved.from_dict(resolved_event.payload)
        self.assertEqual(entity_resolved.entity_id, resolved_event.payload["entity_id"])

        created = self.resolver.resolve("twitter_handle", "roundtrip_alias")
        self.resolver.drain_events()
        alias_event = self.resolver.add_alias(created.entity_id, "email", "rt@example.com")[0]
        entity_alias = entities_module.EntityAliasAdded.from_dict(alias_event.payload)
        self.assertEqual(entity_alias.alias, "rt@example.com")


if __name__ == "__main__":
    unittest.main()

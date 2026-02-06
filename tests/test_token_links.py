import tempfile
import unittest
from pathlib import Path

from metaspn_entities.resolver import EntityResolver
from metaspn_entities.sqlite_backend import SQLiteEntityStore
from metaspn_entities.token_links import (
    attribute_token_outcome,
    link_creator_wallet,
    link_token_to_project,
    resolve_token_entity,
)


class TokenLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_token_contract_resolution_is_deterministic(self) -> None:
        first = resolve_token_entity(
            self.resolver,
            chain="ETH",
            contract_address="0xAbC123",
        )
        second = resolve_token_entity(
            self.resolver,
            chain="eth",
            contract_address="0xabc123",
        )
        self.assertEqual(first.entity_id, second.entity_id)

    def test_multiple_tokens_can_map_to_one_project(self) -> None:
        t1 = resolve_token_entity(self.resolver, chain="eth", contract_address="0x111")
        t2 = resolve_token_entity(self.resolver, chain="eth", contract_address="0x222")

        p1 = link_token_to_project(
            self.resolver,
            token_entity_id=t1.entity_id,
            project_identifier_type="name",
            project_identifier_value="Meta Token Project",
        )
        p2 = link_token_to_project(
            self.resolver,
            token_entity_id=t2.entity_id,
            project_identifier_type="name",
            project_identifier_value="meta token project",
        )

        self.assertEqual(p1, p2)
        aliases = self.resolver.aliases_for_entity(p1)
        token_refs = {a["normalized_value"] for a in aliases if a["identifier_type"] == "token_entity_ref"}
        self.assertIn(t1.entity_id, token_refs)
        self.assertIn(t2.entity_id, token_refs)

    def test_historical_attribution_after_merges(self) -> None:
        old = resolve_token_entity(self.resolver, chain="eth", contract_address="0x999")
        new = resolve_token_entity(self.resolver, chain="eth", contract_address="0xAAA")
        self.resolver.merge_entities(old.entity_id, new.entity_id, reason="token dedupe")

        result = attribute_token_outcome(
            self.resolver,
            {"chain": "ETH", "contract_address": "0x999"},
        )
        self.assertEqual(result.entity_id, new.entity_id)
        self.assertGreater(result.confidence, 0.0)

    def test_creator_wallet_link_is_stable(self) -> None:
        first = link_creator_wallet(self.resolver, creator_wallet="0xBEEF", chain="eth")
        second = link_creator_wallet(self.resolver, creator_wallet="0xbeef", chain="eth")
        self.assertEqual(first.entity_id, second.entity_id)


if __name__ == "__main__":
    unittest.main()

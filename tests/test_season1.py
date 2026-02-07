import tempfile
import unittest
from pathlib import Path

from metaspn_entities.resolver import EntityResolver
from metaspn_entities.season1 import (
    attribute_season_reward,
    canonical_lineage_snapshot,
    player_confidence_summary,
    resolve_founder_wallet,
    resolve_player_wallet,
)
from metaspn_entities.sqlite_backend import SQLiteEntityStore


class Season1HelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "entities.db")
        self.store = SQLiteEntityStore(self.db_path)
        self.resolver = EntityResolver(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tempdir.cleanup()

    def test_player_wallet_resolution_is_deterministic(self) -> None:
        first = resolve_player_wallet(self.resolver, wallet="0xAbC123", chain="ETH")
        second = resolve_player_wallet(self.resolver, wallet="0xabc123", chain="eth")
        self.assertEqual(first.entity_id, second.entity_id)

    def test_wallet_resolution_remains_deterministic_through_merge_and_undo(self) -> None:
        player = resolve_player_wallet(self.resolver, wallet="0x111", chain="eth")
        founder = resolve_founder_wallet(self.resolver, wallet="0x222", chain="eth")

        self.resolver.merge_entities(player.entity_id, founder.entity_id, reason="manual dedupe")
        merged = resolve_player_wallet(self.resolver, wallet="0x111", chain="ETH")
        self.assertEqual(merged.entity_id, founder.entity_id)

        self.resolver.undo_merge(player.entity_id, founder.entity_id)
        unmerged = resolve_player_wallet(self.resolver, wallet="0x111", chain="eth")
        self.assertEqual(unmerged.entity_id, player.entity_id)

    def test_reward_attribution_is_merge_safe(self) -> None:
        old = resolve_player_wallet(self.resolver, wallet="0xOLD", chain="eth")
        new = resolve_player_wallet(self.resolver, wallet="0xNEW", chain="eth")
        self.resolver.merge_entities(old.entity_id, new.entity_id, reason="player dedupe")

        result = attribute_season_reward(
            self.resolver,
            {
                "chain": "ETH",
                "player_wallet": "0xold",
                "player_entity_id": old.entity_id,
            },
        )
        self.assertEqual(result.entity_id, new.entity_id)
        self.assertGreater(result.confidence, 0.0)

    def test_context_helpers_return_canonical_read_models(self) -> None:
        one = resolve_player_wallet(self.resolver, wallet="0xAAA", chain="eth")
        two = resolve_player_wallet(self.resolver, wallet="0xBBB", chain="eth")
        self.resolver.add_alias(one.entity_id, "email", "player@example.com", confidence=0.91)
        self.resolver.merge_entities(one.entity_id, two.entity_id, reason="dedupe")

        summary = player_confidence_summary(self.resolver, one.entity_id)
        self.assertEqual(summary["entity_id"], two.entity_id)
        self.assertIn("by_identifier_type", summary)

        lineage = canonical_lineage_snapshot(self.resolver, one.entity_id)
        self.assertEqual(lineage["canonical_entity_id"], two.entity_id)
        self.assertEqual(lineage["redirect_chain"], [one.entity_id, two.entity_id])
        self.assertGreaterEqual(lineage["merge_count"], 1)


if __name__ == "__main__":
    unittest.main()

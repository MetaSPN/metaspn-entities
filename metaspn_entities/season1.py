from __future__ import annotations

from typing import Any, Dict, Mapping

from .attribution import OutcomeAttribution
from .models import EntityResolution, EntityType
from .normalize import normalize_identifier
from .resolver import EntityResolver


def _normalize_wallet_ref(wallet: str, chain: str) -> str:
    chain_norm = chain.strip().lower() if chain else "eth"
    wallet_norm = normalize_identifier("wallet_address", wallet)
    return f"{chain_norm}:{wallet_norm}"


def resolve_player_wallet(
    resolver: EntityResolver,
    *,
    wallet: str,
    chain: str = "eth",
    caused_by: str = "season1",
) -> EntityResolution:
    wallet_ref = _normalize_wallet_ref(wallet, chain)
    return resolver.resolve(
        "player_wallet",
        wallet_ref,
        context={
            "entity_type": EntityType.PERSON,
            "confidence": 0.97,
            "caused_by": caused_by,
            "provenance": "season1-player-wallet",
        },
    )


def resolve_founder_wallet(
    resolver: EntityResolver,
    *,
    wallet: str,
    chain: str = "eth",
    caused_by: str = "season1",
) -> EntityResolution:
    wallet_ref = _normalize_wallet_ref(wallet, chain)
    return resolver.resolve(
        "founder_wallet",
        wallet_ref,
        context={
            "entity_type": EntityType.PERSON,
            "confidence": 0.98,
            "caused_by": caused_by,
            "provenance": "season1-founder-wallet",
        },
    )


def attribute_season_reward(
    resolver: EntityResolver,
    reward_claim: Mapping[str, Any],
) -> OutcomeAttribution:
    remapped: Dict[str, str] = {}

    chain_value = reward_claim.get("chain")
    chain = chain_value.strip().lower() if isinstance(chain_value, str) and chain_value.strip() else None

    def _map_wallet(ref_key: str, out_key: str) -> None:
        raw = reward_claim.get(ref_key)
        if not isinstance(raw, str) or not raw.strip():
            return
        wallet = raw.strip()
        if ":" in wallet:
            remapped[out_key] = wallet
        elif chain:
            remapped[out_key] = f"{chain}:{wallet}"
        else:
            remapped[out_key] = wallet

    for raw_key in ("entity_id", "player_entity_id", "founder_entity_id"):
        value = reward_claim.get(raw_key)
        if isinstance(value, str) and value.strip():
            remapped["entity_id"] = value.strip()

    _map_wallet("player_wallet", "player_wallet")
    _map_wallet("founder_wallet", "founder_wallet")
    _map_wallet("wallet_address", "wallet_address")
    _map_wallet("claimer_wallet", "wallet_address")

    for raw_key in ("email", "canonical_url", "name", "twitter_handle"):
        value = reward_claim.get(raw_key)
        if isinstance(value, str) and value.strip():
            remapped[raw_key] = value.strip()

    return resolver.attribute_outcome(remapped)


def player_confidence_summary(
    resolver: EntityResolver,
    entity_id: str,
) -> Dict[str, Any]:
    canonical_id = resolver.store.canonical_entity_id(entity_id)
    summary = resolver.confidence_summary(canonical_id)
    return {
        "entity_id": canonical_id,
        "overall_confidence": float(summary["overall_confidence"]),
        "identifier_confidence_avg": float(summary["identifier_confidence_avg"]),
        "alias_confidence_avg": float(summary["alias_confidence_avg"]),
        "unique_source_count": int(summary["unique_source_count"]),
        "evidence_count": int(summary["evidence_count"]),
        "by_identifier_type": dict(summary["by_identifier_type"]),
    }


def canonical_lineage_snapshot(
    resolver: EntityResolver,
    entity_id: str,
) -> Dict[str, Any]:
    chain = [entity_id]
    current = entity_id
    while True:
        next_target = resolver.store.get_redirect_target(current)
        if not next_target:
            break
        chain.append(next_target)
        current = next_target

    canonical_id = resolver.store.canonical_entity_id(entity_id)
    history = resolver.merge_history()
    lineage_merges = [
        item
        for item in history
        if item["from_entity_id"] in chain
        or item["to_entity_id"] in chain
        or item["to_entity_id"] == canonical_id
    ]

    return {
        "requested_entity_id": entity_id,
        "canonical_entity_id": canonical_id,
        "redirect_chain": chain,
        "merge_count": len(lineage_merges),
        "merges": lineage_merges,
    }

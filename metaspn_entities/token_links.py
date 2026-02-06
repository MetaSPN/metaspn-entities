from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from .attribution import OutcomeAttribution
from .models import EntityResolution, EntityType
from .normalize import normalize_identifier
from .resolver import EntityResolver


@dataclass(frozen=True)
class TokenProjectCreatorLinks:
    token_entity_id: str
    project_entity_id: Optional[str]
    creator_entity_id: Optional[str]


def resolve_token_entity(
    resolver: EntityResolver,
    *,
    chain: str,
    contract_address: str,
    caused_by: str = "token-links",
) -> EntityResolution:
    token_ref = f"{chain}:{contract_address}"
    return resolver.resolve(
        "token_contract",
        token_ref,
        context={
            "entity_type": EntityType.PROJECT,
            "confidence": 0.99,
            "caused_by": caused_by,
            "provenance": "token-resolver",
        },
    )


def link_token_to_project(
    resolver: EntityResolver,
    *,
    token_entity_id: str,
    project_identifier_type: str,
    project_identifier_value: str,
    caused_by: str = "token-links",
) -> str:
    project = resolver.resolve(
        project_identifier_type,
        project_identifier_value,
        context={
            "entity_type": EntityType.PROJECT,
            "confidence": 0.92,
            "caused_by": caused_by,
            "provenance": "token-project-link",
        },
    )
    resolver.add_alias(
        project.entity_id,
        "token_entity_ref",
        token_entity_id,
        confidence=0.99,
        caused_by=caused_by,
        provenance="token-project-link",
    )
    return resolver.store.canonical_entity_id(project.entity_id)


def link_creator_wallet(
    resolver: EntityResolver,
    *,
    creator_wallet: str,
    chain: str = "eth",
    caused_by: str = "token-links",
) -> EntityResolution:
    wallet_ref = f"{chain}:{creator_wallet}"
    return resolver.resolve(
        "creator_wallet",
        wallet_ref,
        context={
            "entity_type": EntityType.PERSON,
            "confidence": 0.95,
            "caused_by": caused_by,
            "provenance": "token-creator-link",
        },
    )


def link_token_project_creator(
    resolver: EntityResolver,
    *,
    chain: str,
    contract_address: str,
    project_identifier_type: str,
    project_identifier_value: str,
    creator_wallet: Optional[str] = None,
    caused_by: str = "token-links",
) -> TokenProjectCreatorLinks:
    token = resolve_token_entity(
        resolver,
        chain=chain,
        contract_address=contract_address,
        caused_by=caused_by,
    )
    project_id = link_token_to_project(
        resolver,
        token_entity_id=token.entity_id,
        project_identifier_type=project_identifier_type,
        project_identifier_value=project_identifier_value,
        caused_by=caused_by,
    )
    creator_entity_id: Optional[str] = None
    if creator_wallet:
        creator = link_creator_wallet(
            resolver,
            creator_wallet=creator_wallet,
            chain=chain,
            caused_by=caused_by,
        )
        creator_entity_id = resolver.store.canonical_entity_id(creator.entity_id)
    return TokenProjectCreatorLinks(
        token_entity_id=resolver.store.canonical_entity_id(token.entity_id),
        project_entity_id=project_id,
        creator_entity_id=creator_entity_id,
    )


def attribute_token_outcome(
    resolver: EntityResolver,
    references: Mapping[str, Any],
) -> OutcomeAttribution:
    remapped: Dict[str, str] = {}

    chain = references.get("chain")
    contract = references.get("contract_address")
    if isinstance(chain, str) and chain.strip() and isinstance(contract, str) and contract.strip():
        remapped["token_contract"] = normalize_identifier("token_contract", f"{chain}:{contract}")

    creator_wallet = references.get("creator_wallet")
    if isinstance(creator_wallet, str) and creator_wallet.strip():
        if isinstance(chain, str) and chain.strip():
            remapped["creator_wallet"] = normalize_identifier("creator_wallet", f"{chain}:{creator_wallet}")
        else:
            remapped["creator_wallet"] = normalize_identifier("creator_wallet", creator_wallet)

    for key in ("entity_id", "token_entity_id", "project_entity_id", "email", "canonical_url", "name"):
        value = references.get(key)
        if isinstance(value, str) and value.strip():
            mapped_key = "entity_id" if key in {"token_entity_id", "project_entity_id"} else key
            remapped[mapped_key] = value.strip()

    return resolver.attribute_outcome(remapped)

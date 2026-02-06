from __future__ import annotations

from typing import Any, Dict, Mapping

from .models import EntityType
from .resolver import EntityResolver


def resolve_demo_social_identity(
    resolver: EntityResolver,
    social_payload: Mapping[str, Any],
    *,
    caused_by: str = "demo-pipeline",
) -> Dict[str, Any]:
    platform = str(social_payload.get("platform") or "").strip().lower()
    source = str(social_payload.get("source") or social_payload.get("provenance") or "demo")

    handle = social_payload.get("author_handle") or social_payload.get("handle")
    if not isinstance(handle, str) or not handle.strip():
        raise ValueError("demo payload requires author_handle or handle")
    handle = handle.strip()

    handle_type = f"{platform}_handle" if platform else "handle"
    resolution = resolver.resolve(
        handle_type,
        handle,
        context={
            "entity_type": EntityType.PERSON,
            "caused_by": caused_by,
            "provenance": source,
            "confidence": 0.93,
        },
    )

    for key in ("profile_url", "author_url", "canonical_url"):
        url = social_payload.get(key)
        if isinstance(url, str) and url.strip():
            resolver.add_alias(
                resolution.entity_id,
                "canonical_url",
                url.strip(),
                confidence=0.96,
                caused_by=caused_by,
                provenance=source,
            )
            break

    email = social_payload.get("email")
    if isinstance(email, str) and email.strip():
        resolver.add_alias(
            resolution.entity_id,
            "email",
            email.strip(),
            confidence=0.98,
            caused_by=caused_by,
            provenance=source,
        )

    canonical_id = resolver.store.canonical_entity_id(resolution.entity_id)
    context = resolver.entity_context(canonical_id)
    digest_payload = {
        "entity_id": canonical_id,
        "confidence": context.confidence_summary["overall_confidence"],
        "matched_identifiers": [
            {
                "identifier_type": item["identifier_type"],
                "value": item["value"],
                "confidence": item["confidence"],
                "last_seen_at": item["last_seen_at"],
            }
            for item in context.identifiers
        ],
        "why": {
            "matched_identifier_count": len(context.identifiers),
            "alias_count": len(context.aliases),
            "confidence_summary": context.confidence_summary,
            "relationship_stage_hint": resolver.recommendation_context(canonical_id).relationship_stage_hint,
        },
        "events": [event.payload for event in resolver.drain_events()],
    }
    return digest_payload

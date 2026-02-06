from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .events import EmittedEvent
from .models import EntityType
from .resolver import EntityResolver


@dataclass(frozen=True)
class SignalResolutionResult:
    entity_id: str
    confidence: float
    emitted_events: List[EmittedEvent]


def resolve_normalized_social_signal(
    resolver: EntityResolver,
    signal_envelope: Mapping[str, Any] | Any,
    *,
    default_entity_type: str = EntityType.PERSON,
    caused_by: str = "m0-ingestion",
) -> SignalResolutionResult:
    """Resolve a normalized social signal envelope into a canonical entity.

    The adapter is intentionally deterministic:
    - Identifier extraction order is fixed.
    - Primary resolution always uses the highest-priority available identifier.
    - Remaining identifiers are added as aliases in deterministic order.
    """

    # Keep adapter call output scoped to actions taken in this invocation only.
    resolver.drain_events()

    envelope = _coerce_envelope(signal_envelope)
    payload = _coerce_payload(envelope.get("payload"))
    source = str(envelope.get("source") or "unknown-source")

    identifiers = _extract_identifiers(payload)
    if not identifiers:
        raise ValueError("No resolvable identifiers found in normalized social signal payload")

    primary_type, primary_value, primary_confidence = identifiers[0]
    resolution = resolver.resolve(
        primary_type,
        primary_value,
        context={
            "confidence": primary_confidence,
            "entity_type": default_entity_type,
            "caused_by": caused_by,
            "provenance": source,
        },
    )

    for alias_type, alias_value, alias_confidence in identifiers[1:]:
        resolver.add_alias(
            resolution.entity_id,
            alias_type,
            alias_value,
            confidence=alias_confidence,
            caused_by=caused_by,
            provenance=source,
        )

    emitted = resolver.drain_events()
    return SignalResolutionResult(
        entity_id=resolution.entity_id,
        confidence=resolution.confidence,
        emitted_events=emitted,
    )


def _coerce_envelope(signal_envelope: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if isinstance(signal_envelope, Mapping):
        return dict(signal_envelope)
    if hasattr(signal_envelope, "to_dict") and callable(signal_envelope.to_dict):
        return dict(signal_envelope.to_dict())
    raise TypeError("signal_envelope must be a mapping or provide to_dict()")


def _coerce_payload(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        return dict(payload)
    if hasattr(payload, "to_dict") and callable(payload.to_dict):
        return dict(payload.to_dict())
    raise TypeError("signal payload must be a mapping or provide to_dict()")


def _extract_identifiers(payload: Dict[str, Any]) -> List[Tuple[str, str, float]]:
    platform = str(payload.get("platform") or "").strip().lower()

    candidates: List[Tuple[int, str, str, float]] = []

    # Highest confidence identifiers first.
    if isinstance(payload.get("email"), str) and payload["email"].strip():
        candidates.append((0, "email", payload["email"].strip(), 0.98))

    for key in ("profile_url", "author_url", "canonical_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append((1, "canonical_url", value.strip(), 0.96))
            break

    handle = payload.get("author_handle") or payload.get("handle")
    if isinstance(handle, str) and handle.strip():
        handle_type = f"{platform}_handle" if platform else "handle"
        candidates.append((2, handle_type, handle.strip(), 0.93))

    if isinstance(payload.get("domain"), str) and payload["domain"].strip():
        candidates.append((3, "domain", payload["domain"].strip(), 0.9))

    for key in ("display_name", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append((4, "name", value.strip(), 0.7))
            break

    # Deduplicate by (identifier_type, raw value) while preserving deterministic order.
    seen: set[Tuple[str, str]] = set()
    ordered: List[Tuple[str, str, float]] = []
    for _, id_type, id_value, confidence in sorted(candidates, key=lambda c: (c[0], c[1], c[2])):
        key = (id_type, id_value)
        if key in seen:
            continue
        seen.add(key)
        ordered.append((id_type, id_value, confidence))

    return ordered

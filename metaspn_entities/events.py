from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

DEFAULT_SCHEMA_VERSION = "0.1"
try:
    from metaspn_schemas.core import DEFAULT_SCHEMA_VERSION as _SCHEMA_VERSION

    DEFAULT_SCHEMA_VERSION = _SCHEMA_VERSION
except Exception:
    # Keep local behavior deterministic when dependency is not importable in dev sandboxes.
    pass


@dataclass(frozen=True)
class EmittedEvent:
    event_type: str
    payload: Dict[str, Any]


class EventFactory:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(microsecond=0)

    @staticmethod
    def entity_resolved(entity_id: str, resolver: str, confidence: float) -> EmittedEvent:
        return EmittedEvent(
            event_type="EntityResolved",
            payload={
                "entity_id": entity_id,
                "resolver": resolver,
                "resolved_at": EventFactory._now().isoformat(),
                "confidence": confidence,
                "schema_version": DEFAULT_SCHEMA_VERSION,
            },
        )

    @staticmethod
    def entity_merged(entity_id: str, merged_from: tuple[str, ...], reason: str | None = None) -> EmittedEvent:
        return EmittedEvent(
            event_type="EntityMerged",
            payload={
                "entity_id": entity_id,
                "merged_from": list(merged_from),
                "merged_at": EventFactory._now().isoformat(),
                "reason": reason,
                "schema_version": DEFAULT_SCHEMA_VERSION,
            },
        )

    @staticmethod
    def entity_alias_added(entity_id: str, alias: str, alias_type: str) -> EmittedEvent:
        return EmittedEvent(
            event_type="EntityAliasAdded",
            payload={
                "entity_id": entity_id,
                "alias": alias,
                "alias_type": alias_type,
                "added_at": EventFactory._now().isoformat(),
                "schema_version": DEFAULT_SCHEMA_VERSION,
            },
        )

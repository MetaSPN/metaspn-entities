from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class EmittedEvent:
    event_type: str
    payload: Dict[str, Any]


class EventFactory:
    @staticmethod
    def entity_resolved(entity_id: str, identifier_type: str, value: str, confidence: float, created_new_entity: bool) -> EmittedEvent:
        return EmittedEvent(
            event_type="EntityResolved",
            payload={
                "entity_id": entity_id,
                "identifier_type": identifier_type,
                "value": value,
                "confidence": confidence,
                "created_new_entity": created_new_entity,
            },
        )

    @staticmethod
    def entity_merged(from_entity_id: str, to_entity_id: str, reason: str, caused_by: str) -> EmittedEvent:
        return EmittedEvent(
            event_type="EntityMerged",
            payload={
                "from_entity_id": from_entity_id,
                "to_entity_id": to_entity_id,
                "reason": reason,
                "caused_by": caused_by,
            },
        )

    @staticmethod
    def entity_alias_added(entity_id: str, identifier_type: str, normalized_value: str, caused_by: str) -> EmittedEvent:
        return EmittedEvent(
            event_type="EntityAliasAdded",
            payload={
                "entity_id": entity_id,
                "identifier_type": identifier_type,
                "normalized_value": normalized_value,
                "caused_by": caused_by,
            },
        )

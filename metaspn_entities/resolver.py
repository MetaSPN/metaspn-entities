from __future__ import annotations

from typing import Any, Dict, List, Optional

from .context import RecommendationContext, EntityContext, build_confidence_summary, build_recommendation_context
from .events import EmittedEvent, EventFactory
from .models import (
    DEFAULT_MATCH_CONFIDENCE,
    DEFAULT_NEW_ENTITY_CONFIDENCE,
    EntityResolution,
    EntityStatus,
    EntityType,
)
from .normalize import AUTO_MERGE_IDENTIFIER_TYPES, normalize_identifier
from .sqlite_backend import SQLiteEntityStore


class EntityResolver:
    def __init__(self, store: Optional[SQLiteEntityStore] = None) -> None:
        self.store = store or SQLiteEntityStore()
        self._event_buffer: List[EmittedEvent] = []

    def resolve(self, identifier_type: str, value: str, context: Optional[Dict[str, Any]] = None) -> EntityResolution:
        context = context or {}
        confidence = float(context.get("confidence", DEFAULT_MATCH_CONFIDENCE))
        provenance = context.get("provenance")
        entity_type = context.get("entity_type", EntityType.PERSON)
        caused_by = context.get("caused_by", "resolver")

        normalized = normalize_identifier(identifier_type, value)
        self.store.upsert_identifier(identifier_type, value, normalized, confidence, provenance)

        existing_alias = self.store.find_alias(identifier_type, normalized)
        if existing_alias:
            entity_id = self.store.canonical_entity_id(existing_alias["entity_id"])
            matched_identifiers = list(self.store.iter_identifiers_for_entity(entity_id))
            resolution = EntityResolution(
                entity_id=entity_id,
                confidence=max(float(existing_alias["confidence"]), confidence),
                created_new_entity=False,
                matched_identifiers=matched_identifiers,
            )
            self._event_buffer.append(EventFactory.entity_resolved(entity_id, caused_by, resolution.confidence))
            return resolution

        entity_id = self.store.create_entity(entity_type)
        created_entity_id = entity_id
        added, conflicting_entity_id = self.store.add_alias(
            identifier_type=identifier_type,
            normalized_value=normalized,
            entity_id=entity_id,
            confidence=confidence,
            caused_by=caused_by,
            provenance=provenance,
        )

        if conflicting_entity_id and identifier_type in AUTO_MERGE_IDENTIFIER_TYPES:
            merge_reason = f"auto-merge on {identifier_type}:{normalized}"
            self.store.merge_entities(entity_id, conflicting_entity_id, merge_reason, "auto-merge")
            entity_id = self.store.canonical_entity_id(conflicting_entity_id)
            self._event_buffer.append(EventFactory.entity_merged(entity_id, (created_entity_id,), merge_reason))

        matched_identifiers = list(self.store.iter_identifiers_for_entity(entity_id))
        resolution = EntityResolution(
            entity_id=entity_id,
            confidence=confidence if added else DEFAULT_NEW_ENTITY_CONFIDENCE,
            created_new_entity=True,
            matched_identifiers=matched_identifiers,
        )
        if added:
            self._event_buffer.append(EventFactory.entity_alias_added(entity_id, normalized, identifier_type))
        self._event_buffer.append(EventFactory.entity_resolved(entity_id, caused_by, resolution.confidence))
        return resolution

    def add_alias(
        self,
        entity_id: str,
        identifier_type: str,
        value: str,
        confidence: float = DEFAULT_MATCH_CONFIDENCE,
        caused_by: str = "manual",
        provenance: Optional[str] = None,
    ) -> List[EmittedEvent]:
        self.store.ensure_entity(entity_id)
        canonical_entity_id = self.store.canonical_entity_id(entity_id)
        normalized = normalize_identifier(identifier_type, value)
        self.store.upsert_identifier(identifier_type, value, normalized, confidence, provenance)

        added, conflicting_entity_id = self.store.add_alias(
            identifier_type=identifier_type,
            normalized_value=normalized,
            entity_id=canonical_entity_id,
            confidence=confidence,
            caused_by=caused_by,
            provenance=provenance,
        )
        if conflicting_entity_id and conflicting_entity_id != canonical_entity_id:
            if identifier_type in AUTO_MERGE_IDENTIFIER_TYPES:
                reason = f"auto-merge on {identifier_type}:{normalized}"
                self.store.merge_entities(canonical_entity_id, conflicting_entity_id, reason, "auto-merge")
                event = EventFactory.entity_merged(conflicting_entity_id, (canonical_entity_id,), reason)
                self._event_buffer.append(event)
                return [event]
            raise ValueError(
                f"Alias already mapped to another entity: {identifier_type}:{normalized} -> {conflicting_entity_id}"
            )

        if not added:
            return []

        event = EventFactory.entity_alias_added(canonical_entity_id, normalized, identifier_type)
        self._event_buffer.append(event)
        return [event]

    def merge_entities(self, from_entity_id: str, to_entity_id: str, reason: str, caused_by: str = "manual") -> EmittedEvent:
        self.store.ensure_entity(from_entity_id)
        self.store.ensure_entity(to_entity_id)
        self.store.merge_entities(from_entity_id, to_entity_id, reason, caused_by)
        event = EventFactory.entity_merged(self.store.canonical_entity_id(to_entity_id), (from_entity_id,), reason)
        self._event_buffer.append(event)
        return event

    def undo_merge(self, from_entity_id: str, to_entity_id: str, caused_by: str = "manual") -> EmittedEvent:
        reason = f"undo merge {from_entity_id}->{to_entity_id}"
        if self.store.get_redirect_target(from_entity_id) == to_entity_id:
            self.store.remove_redirect(from_entity_id)
            self.store.set_entity_status(from_entity_id, EntityStatus.ACTIVE)
        self.store.merge_entities(to_entity_id, from_entity_id, reason, caused_by)
        event = EventFactory.entity_merged(self.store.canonical_entity_id(from_entity_id), (to_entity_id,), reason)
        self._event_buffer.append(event)
        return event

    def merge_history(self) -> List[Dict[str, Any]]:
        return self.store.list_merge_history()

    def aliases_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        return self.store.list_aliases_for_entity(entity_id)

    def confidence_summary(self, entity_id: str) -> Dict[str, Any]:
        canonical_id = self.store.canonical_entity_id(entity_id)
        aliases = self.store.list_aliases_for_entity(canonical_id)
        identifiers = self.store.list_identifier_records_for_entity(canonical_id)
        return build_confidence_summary(aliases, identifiers, identifiers)

    def entity_context(self, entity_id: str, recent_limit: int = 10) -> EntityContext:
        canonical_id = self.store.canonical_entity_id(entity_id)
        aliases = self.store.list_aliases_for_entity(canonical_id)
        identifiers = self.store.list_identifier_records_for_entity(canonical_id)
        recent_evidence = sorted(
            identifiers,
            key=lambda row: (str(row["last_seen_at"]), str(row["identifier_type"]), str(row["normalized_value"])),
            reverse=True,
        )[: max(recent_limit, 0)]
        summary = build_confidence_summary(aliases, identifiers, recent_evidence)
        return EntityContext(
            entity_id=canonical_id,
            aliases=aliases,
            identifiers=identifiers,
            recent_evidence=recent_evidence,
            confidence_summary=summary,
        )

    def recommendation_context(self, entity_id: str) -> RecommendationContext:
        canonical_id = self.store.canonical_entity_id(entity_id)
        aliases = self.store.list_aliases_for_entity(canonical_id)
        identifiers = self.store.list_identifier_records_for_entity(canonical_id)
        return build_recommendation_context(canonical_id, aliases, identifiers)

    def export_snapshot(self, output_path: str) -> None:
        self.store.export_snapshot(output_path)

    def drain_events(self) -> List[EmittedEvent]:
        events = list(self._event_buffer)
        self._event_buffer.clear()
        return events

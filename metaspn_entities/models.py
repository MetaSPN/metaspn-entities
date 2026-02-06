from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


DEFAULT_MATCH_CONFIDENCE = 0.95
DEFAULT_NEW_ENTITY_CONFIDENCE = 0.6


class EntityStatus:
    ACTIVE = "active"
    MERGED = "merged"


class EntityType:
    PERSON = "person"
    ORG = "org"
    PROJECT = "project"


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    created_at: str
    status: str


@dataclass(frozen=True)
class Identifier:
    identifier_type: str
    value: str
    normalized_value: str
    confidence: float
    first_seen_at: str
    last_seen_at: str
    provenance: Optional[str] = None


@dataclass(frozen=True)
class Alias:
    identifier_type: str
    normalized_value: str
    entity_id: str
    confidence: float
    created_at: str
    caused_by: str
    provenance: Optional[str] = None


@dataclass(frozen=True)
class MergeRecord:
    merge_id: int
    from_entity_id: str
    to_entity_id: str
    reason: str
    timestamp: str
    caused_by: str


@dataclass(frozen=True)
class EntityResolution:
    entity_id: str
    confidence: float
    created_new_entity: bool
    matched_identifiers: List[Dict[str, Any]] = field(default_factory=list)



def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

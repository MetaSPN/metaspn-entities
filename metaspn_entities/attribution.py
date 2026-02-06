from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .normalize import normalize_identifier


@dataclass(frozen=True)
class OutcomeAttribution:
    entity_id: Optional[str]
    confidence: float
    matched_references: List[Dict[str, Any]] = field(default_factory=list)
    strategy: str = "confidence-weighted-reference-v1"


def normalize_outcome_references(references: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> List[Tuple[str, str]]:
    refs: List[Tuple[str, str]] = []
    if isinstance(references, Mapping):
        for raw_type in sorted(references):
            value = references[raw_type]
            if value is None:
                continue
            if isinstance(value, str) and value.strip():
                refs.append((str(raw_type), value.strip()))
        return refs

    for item in references:
        id_type = str(item.get("identifier_type") or item.get("type") or "").strip()
        value = str(item.get("value") or "").strip()
        if not id_type or not value:
            continue
        refs.append((id_type, value))
    return refs


def rank_entity_candidates(
    references: Iterable[Tuple[str, str]],
    resolve_reference: Any,
) -> OutcomeAttribution:
    candidate_scores: Dict[str, float] = {}
    candidate_hits: Dict[str, int] = {}
    matched: List[Dict[str, Any]] = []
    total_refs = 0

    for identifier_type, value in references:
        total_refs += 1
        match = resolve_reference(identifier_type, value)
        matched.append(
            {
                "identifier_type": identifier_type,
                "value": value,
                "normalized_value": match.get("normalized_value"),
                "matched_entity_id": match.get("entity_id"),
                "reference_confidence": float(match.get("confidence", 0.0)),
            }
        )
        entity_id = match.get("entity_id")
        confidence = float(match.get("confidence", 0.0))
        if entity_id:
            candidate_scores[entity_id] = candidate_scores.get(entity_id, 0.0) + confidence
            candidate_hits[entity_id] = candidate_hits.get(entity_id, 0) + 1

    if not candidate_scores:
        return OutcomeAttribution(entity_id=None, confidence=0.0, matched_references=matched)

    ranked = sorted(
        candidate_scores.items(),
        key=lambda kv: (
            -kv[1],
            -candidate_hits.get(kv[0], 0),
            kv[0],
        ),
    )
    best_entity_id, best_score = ranked[0]
    denom = max(1, total_refs)
    normalized_confidence = min(1.0, round(best_score / float(denom), 6))
    return OutcomeAttribution(
        entity_id=best_entity_id,
        confidence=normalized_confidence,
        matched_references=matched,
    )


def normalize_reference(identifier_type: str, value: str) -> Tuple[str, str]:
    if identifier_type == "entity_id":
        return identifier_type, value
    return identifier_type, normalize_identifier(identifier_type, value)

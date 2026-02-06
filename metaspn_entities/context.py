from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class EntityContext:
    entity_id: str
    aliases: List[Dict[str, Any]]
    identifiers: List[Dict[str, Any]]
    recent_evidence: List[Dict[str, Any]]
    confidence_summary: Dict[str, Any]


def build_confidence_summary(
    aliases: List[Dict[str, Any]],
    identifiers: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    identifier_confidences = sorted(float(item["confidence"]) for item in identifiers)
    alias_confidences = sorted(float(item["confidence"]) for item in aliases)
    source_set = sorted(
        {
            str(item.get("provenance"))
            for item in evidence
            if item.get("provenance") not in (None, "")
        }
    )

    identifier_avg = _avg(identifier_confidences)
    alias_avg = _avg(alias_confidences)
    source_diversity = min(1.0, len(source_set) / 3.0)

    overall = min(1.0, (0.65 * identifier_avg) + (0.25 * alias_avg) + (0.10 * source_diversity))
    by_identifier_type = _rollup_by_identifier_type(identifiers)

    return {
        "overall_confidence": round(overall, 6),
        "identifier_confidence_avg": round(identifier_avg, 6),
        "alias_confidence_avg": round(alias_avg, 6),
        "unique_source_count": len(source_set),
        "evidence_count": len(evidence),
        "by_identifier_type": by_identifier_type,
    }


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _rollup_by_identifier_type(identifiers: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[float]] = {}
    for item in identifiers:
        key = str(item["identifier_type"])
        grouped.setdefault(key, []).append(float(item["confidence"]))

    rollup: Dict[str, Dict[str, float]] = {}
    for key in sorted(grouped):
        values = sorted(grouped[key])
        rollup[key] = {
            "count": float(len(values)),
            "avg_confidence": round(_avg(values), 6),
            "max_confidence": round(max(values), 6),
        }
    return rollup

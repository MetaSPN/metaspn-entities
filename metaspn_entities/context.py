from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class EntityContext:
    entity_id: str
    aliases: List[Dict[str, Any]]
    identifiers: List[Dict[str, Any]]
    recent_evidence: List[Dict[str, Any]]
    confidence_summary: Dict[str, Any]


@dataclass(frozen=True)
class RecommendationContext:
    entity_id: str
    identity_confidence: float
    activity_recency_days: float
    interaction_history_summary: Dict[str, Any]
    preferred_channel_hint: str
    relationship_stage_hint: str
    continuity: Dict[str, Any]


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


def build_recommendation_context(
    entity_id: str,
    aliases: List[Dict[str, Any]],
    identifiers: List[Dict[str, Any]],
    *,
    now: datetime | None = None,
) -> RecommendationContext:
    current_now = now or datetime.now(timezone.utc)
    evidence_count = len(identifiers)
    recent_seen = _latest_seen(identifiers)
    activity_recency_days = _recency_days(recent_seen, current_now)

    summary = build_confidence_summary(aliases, identifiers, identifiers)
    preferred_channel = _preferred_channel_hint(identifiers)
    relationship_stage = _relationship_stage_hint(
        evidence_count=evidence_count,
        recency_days=activity_recency_days,
        confidence=summary["overall_confidence"],
    )

    provenance_counts: Dict[str, int] = {}
    for item in identifiers:
        provenance = str(item.get("provenance") or "unknown")
        provenance_counts[provenance] = provenance_counts.get(provenance, 0) + 1

    interaction_history_summary = {
        "evidence_count": evidence_count,
        "distinct_sources": len(provenance_counts),
        "sources": {k: provenance_counts[k] for k in sorted(provenance_counts)},
    }

    continuity = {
        "canonical_entity_id": entity_id,
        "alias_count": len(aliases),
        "identifier_count": len(identifiers),
    }

    return RecommendationContext(
        entity_id=entity_id,
        identity_confidence=float(summary["overall_confidence"]),
        activity_recency_days=activity_recency_days,
        interaction_history_summary=interaction_history_summary,
        preferred_channel_hint=preferred_channel,
        relationship_stage_hint=relationship_stage,
        continuity=continuity,
    )


def _latest_seen(identifiers: List[Dict[str, Any]]) -> datetime | None:
    timestamps = [
        _parse_iso(str(item.get("last_seen_at")))
        for item in identifiers
        if item.get("last_seen_at")
    ]
    clean = [ts for ts in timestamps if ts is not None]
    if not clean:
        return None
    return max(clean)


def _parse_iso(raw: str) -> datetime | None:
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _recency_days(last_seen: datetime | None, now: datetime) -> float:
    if last_seen is None:
        return float("inf")
    delta = now - last_seen
    seconds = max(0.0, delta.total_seconds())
    return round(seconds / 86400.0, 6)


def _preferred_channel_hint(identifiers: List[Dict[str, Any]]) -> str:
    weights = {
        "email": 5,
        "linkedin_handle": 4,
        "twitter_handle": 3,
        "github_handle": 3,
        "canonical_url": 2,
        "domain": 1,
        "name": 0,
    }
    scores: Dict[str, int] = {}
    for item in identifiers:
        id_type = str(item["identifier_type"])
        score = weights.get(id_type, 1)
        scores[id_type] = scores.get(id_type, 0) + score
    if not scores:
        return "unknown"
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _relationship_stage_hint(*, evidence_count: int, recency_days: float, confidence: float) -> str:
    if evidence_count >= 6 and recency_days <= 30 and confidence >= 0.8:
        return "engaged"
    if evidence_count >= 3 and recency_days <= 90 and confidence >= 0.65:
        return "warm"
    return "cold"

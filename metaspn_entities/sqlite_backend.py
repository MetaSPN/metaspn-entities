from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import EntityStatus, utcnow_iso


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identifiers (
  identifier_type TEXT NOT NULL,
  value TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  confidence REAL NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  provenance TEXT,
  UNIQUE(identifier_type, normalized_value)
);

CREATE TABLE IF NOT EXISTS aliases (
  identifier_type TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  caused_by TEXT NOT NULL,
  provenance TEXT,
  UNIQUE(identifier_type, normalized_value)
);

CREATE TABLE IF NOT EXISTS merge_records (
  merge_id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_entity_id TEXT NOT NULL,
  to_entity_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  caused_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_redirects (
  from_entity_id TEXT PRIMARY KEY,
  to_entity_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  reason TEXT NOT NULL,
  caused_by TEXT NOT NULL
);
"""


class SQLiteEntityStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_entity(self, entity_type: str) -> str:
        entity_id = f"ent_{uuid.uuid4().hex}"
        now = utcnow_iso()
        self.conn.execute(
            "INSERT INTO entities(entity_id, entity_type, created_at, status) VALUES (?, ?, ?, ?)",
            (entity_id, entity_type, now, EntityStatus.ACTIVE),
        )
        self.conn.commit()
        return entity_id

    def get_entity(self, entity_id: str) -> Optional[sqlite3.Row]:
        row = self.conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        return row

    def canonical_entity_id(self, entity_id: str) -> str:
        current = entity_id
        visited = set()
        while True:
            if current in visited:
                raise ValueError(f"Cycle detected in merge redirects for {entity_id}")
            visited.add(current)
            row = self.conn.execute(
                "SELECT to_entity_id FROM entity_redirects WHERE from_entity_id = ?", (current,)
            ).fetchone()
            if not row:
                return current
            current = row["to_entity_id"]

    def find_alias(self, identifier_type: str, normalized_value: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM aliases WHERE identifier_type = ? AND normalized_value = ?",
            (identifier_type, normalized_value),
        ).fetchone()

    def upsert_identifier(
        self,
        identifier_type: str,
        value: str,
        normalized_value: str,
        confidence: float,
        provenance: Optional[str],
    ) -> None:
        now = utcnow_iso()
        existing = self.conn.execute(
            "SELECT * FROM identifiers WHERE identifier_type = ? AND normalized_value = ?",
            (identifier_type, normalized_value),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE identifiers SET value = ?, confidence = ?, last_seen_at = ?, provenance = ? WHERE identifier_type = ? AND normalized_value = ?",
                (
                    value,
                    max(confidence, existing["confidence"]),
                    now,
                    provenance or existing["provenance"],
                    identifier_type,
                    normalized_value,
                ),
            )
        else:
            self.conn.execute(
                "INSERT INTO identifiers(identifier_type, value, normalized_value, confidence, first_seen_at, last_seen_at, provenance) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (identifier_type, value, normalized_value, confidence, now, now, provenance),
            )
        self.conn.commit()

    def add_alias(
        self,
        identifier_type: str,
        normalized_value: str,
        entity_id: str,
        confidence: float,
        caused_by: str,
        provenance: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        now = utcnow_iso()
        existing = self.find_alias(identifier_type, normalized_value)
        canonical_target = self.canonical_entity_id(entity_id)

        if existing:
            existing_entity = self.canonical_entity_id(existing["entity_id"])
            if existing_entity == canonical_target:
                self.conn.execute(
                    "UPDATE aliases SET confidence = ?, provenance = ? WHERE identifier_type = ? AND normalized_value = ?",
                    (
                        max(confidence, existing["confidence"]),
                        provenance or existing["provenance"],
                        identifier_type,
                        normalized_value,
                    ),
                )
                self.conn.commit()
                return False, None
            return False, existing_entity

        self.conn.execute(
            "INSERT INTO aliases(identifier_type, normalized_value, entity_id, confidence, created_at, caused_by, provenance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (identifier_type, normalized_value, canonical_target, confidence, now, caused_by, provenance),
        )
        self.conn.commit()
        return True, None

    def reassign_aliases(self, from_entity_id: str, to_entity_id: str) -> None:
        self.conn.execute(
            "UPDATE aliases SET entity_id = ? WHERE entity_id = ?",
            (to_entity_id, from_entity_id),
        )

    def get_redirect_target(self, from_entity_id: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT to_entity_id FROM entity_redirects WHERE from_entity_id = ?",
            (from_entity_id,),
        ).fetchone()
        if not row:
            return None
        return str(row["to_entity_id"])

    def remove_redirect(self, from_entity_id: str) -> None:
        self.conn.execute("DELETE FROM entity_redirects WHERE from_entity_id = ?", (from_entity_id,))
        self.conn.commit()

    def set_entity_status(self, entity_id: str, status: str) -> None:
        self.conn.execute("UPDATE entities SET status = ? WHERE entity_id = ?", (status, entity_id))
        self.conn.commit()

    def merge_entities(self, from_entity_id: str, to_entity_id: str, reason: str, caused_by: str) -> int:
        from_canonical = self.canonical_entity_id(from_entity_id)
        to_canonical = self.canonical_entity_id(to_entity_id)

        if from_canonical == to_canonical:
            raise ValueError("Entities are already merged")

        timestamp = utcnow_iso()
        self.conn.execute(
            "INSERT OR REPLACE INTO entity_redirects(from_entity_id, to_entity_id, timestamp, reason, caused_by) VALUES (?, ?, ?, ?, ?)",
            (from_canonical, to_canonical, timestamp, reason, caused_by),
        )
        self.conn.execute(
            "UPDATE entities SET status = ? WHERE entity_id = ?",
            (EntityStatus.MERGED, from_canonical),
        )
        self.conn.execute(
            "UPDATE entities SET status = ? WHERE entity_id = ?",
            (EntityStatus.ACTIVE, to_canonical),
        )
        cursor = self.conn.execute(
            "INSERT INTO merge_records(from_entity_id, to_entity_id, reason, timestamp, caused_by) VALUES (?, ?, ?, ?, ?)",
            (from_canonical, to_canonical, reason, timestamp, caused_by),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def list_aliases_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        target = self.canonical_entity_id(entity_id)
        rows = self.conn.execute(
            "SELECT identifier_type, normalized_value, entity_id, confidence FROM aliases ORDER BY identifier_type, normalized_value"
        ).fetchall()
        return [
            {
                "identifier_type": row["identifier_type"],
                "normalized_value": row["normalized_value"],
                "entity_id": row["entity_id"],
                "confidence": row["confidence"],
            }
            for row in rows
            if self.canonical_entity_id(row["entity_id"]) == target
        ]

    def list_merge_history(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT merge_id, from_entity_id, to_entity_id, reason, timestamp, caused_by FROM merge_records ORDER BY merge_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def export_snapshot(self, output_path: str) -> None:
        payload: Dict[str, Any] = {}
        for table in ["entities", "identifiers", "aliases", "merge_records", "entity_redirects"]:
            rows = self.conn.execute(f"SELECT * FROM {table}").fetchall()
            payload[table] = [dict(row) for row in rows]

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def ensure_entity(self, entity_id: str) -> None:
        row = self.get_entity(entity_id)
        if not row:
            raise ValueError(f"Unknown entity_id: {entity_id}")

    def iter_identifiers_for_entity(self, entity_id: str) -> Iterable[Dict[str, Any]]:
        target = self.canonical_entity_id(entity_id)
        rows = self.conn.execute(
            """
            SELECT a.entity_id, i.identifier_type, i.value, i.normalized_value, i.confidence
            FROM aliases a
            JOIN identifiers i ON a.identifier_type = i.identifier_type AND a.normalized_value = i.normalized_value
            ORDER BY i.identifier_type, i.normalized_value
            """
        ).fetchall()
        for row in rows:
            if self.canonical_entity_id(row["entity_id"]) == target:
                yield {
                    "identifier_type": row["identifier_type"],
                    "value": row["value"],
                    "normalized_value": row["normalized_value"],
                    "confidence": row["confidence"],
                }

    def list_identifier_records_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        target = self.canonical_entity_id(entity_id)
        rows = self.conn.execute(
            """
            SELECT
              a.entity_id,
              i.identifier_type,
              i.value,
              i.normalized_value,
              i.confidence,
              i.first_seen_at,
              i.last_seen_at,
              i.provenance
            FROM aliases a
            JOIN identifiers i
              ON a.identifier_type = i.identifier_type
             AND a.normalized_value = i.normalized_value
            ORDER BY i.identifier_type, i.normalized_value
            """
        ).fetchall()
        return [
            {
                "identifier_type": row["identifier_type"],
                "value": row["value"],
                "normalized_value": row["normalized_value"],
                "confidence": row["confidence"],
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
                "provenance": row["provenance"],
            }
            for row in rows
            if self.canonical_entity_id(row["entity_id"]) == target
        ]

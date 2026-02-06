# metaspn-entities

Identity layer for MetaSPN systems.

## Features

- Canonical entity IDs
- Deterministic identifier normalization + alias resolution
- Merge history and reversible soft undo
- SQLite backend using stdlib `sqlite3`
- Event emission payloads for `EntityResolved`, `EntityMerged`, `EntityAliasAdded`
- Optional filesystem snapshot export

## Quick usage

```python
from metaspn_entities import EntityResolver

resolver = EntityResolver()
resolution = resolver.resolve("twitter_handle", "@some_handle")
events = resolver.drain_events()
print(resolution.entity_id, resolution.confidence)
```

## API notes

- `resolve(identifier_type, value, context=None) -> EntityResolution`
- `add_alias(entity_id, identifier_type, value, ...)`
- `merge_entities(from_entity_id, to_entity_id, reason, ...)`
- `undo_merge(from_entity_id, to_entity_id, ...)` (implemented as reverse merge with redirect correction)
- `drain_events() -> list[EmittedEvent]`
- `export_snapshot(output_path)` to inspect SQLite state as JSON

## Event Contract Guarantees

`drain_events()` returns `EmittedEvent` objects whose `event_type` and `payload` are
schema-compatible with `metaspn-schemas` entity events.

- `EntityResolved` payload keys:
  - `entity_id`, `resolver`, `resolved_at`, `confidence`, `schema_version`
- `EntityMerged` payload keys:
  - `entity_id`, `merged_from`, `merged_at`, `reason`, `schema_version`
- `EntityAliasAdded` payload keys:
  - `entity_id`, `alias`, `alias_type`, `added_at`, `schema_version`

Datetime fields are emitted as UTC ISO-8601 strings for deterministic serialization.

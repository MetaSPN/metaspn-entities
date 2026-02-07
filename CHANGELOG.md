# Changelog

## 0.1.10 - 2026-02-07

### Added
- Season 1 helper module in `/Users/leoguinan/MetaSPN/metaspn-entities/metaspn_entities/season1.py`:
  - `resolve_player_wallet`
  - `resolve_founder_wallet`
  - `attribute_season_reward`
  - `player_confidence_summary`
  - `canonical_lineage_snapshot`
- Season 1 deterministic/merge-safe tests in `/Users/leoguinan/MetaSPN/metaspn-entities/tests/test_season1.py` for:
  - wallet resolution determinism
  - alias/merge/undo continuity
  - reward attribution stability across merge redirects
  - canonical confidence/lineage read models

### Changed
- Normalization support expanded for Season 1 wallet identifiers:
  - `player_wallet`
  - `founder_wallet`
- Public exports now include all Season 1 helpers.

## 0.1.9 - 2026-02-06

### Added
- Token/project/creator linkage helpers in `/Users/leoguinan/MetaSPN/metaspn-entities/metaspn_entities/token_links.py`:
  - `resolve_token_entity`
  - `link_token_to_project`
  - `link_creator_wallet`
  - `link_token_project_creator`
  - `attribute_token_outcome`
- Token linkage tests in `/Users/leoguinan/MetaSPN/metaspn-entities/tests/test_token_links.py`:
  - deterministic contract resolution
  - multiple tokens to one project entity mapping
  - merge-safe historical attribution
  - creator wallet stability

### Changed
- Normalization coverage expanded for `token_contract`, `wallet_address`, and `creator_wallet`.
- Public exports now include token link helpers and `TokenProjectCreatorLinks`.

## 0.1.8 - 2026-02-06

### Added
- Demo-focused helper in `/Users/leoguinan/MetaSPN/metaspn-entities/metaspn_entities/demo.py`:
  - `resolve_demo_social_identity(resolver, social_payload)`
- Digest-ready explainability payload fields:
  - confidence
  - matched identifiers
  - `why` section with confidence rollup and relationship hint
- Demo stability tests in `/Users/leoguinan/MetaSPN/metaspn-entities/tests/test_demo_support.py` for:
  - repeated-day stable resolution
  - alias collision continuity
  - explainability payload structure

### Changed
- Normalization coverage now includes additional demo platform handle types (e.g. `x_handle`, `linkedin_handle`, `bluesky_handle`).
- Public exports now include `resolve_demo_social_identity`.

## 0.1.7 - 2026-02-06

### Added
- Outcome attribution model and helpers in `/Users/leoguinan/MetaSPN/metaspn-entities/metaspn_entities/attribution.py`:
  - `OutcomeAttribution`
  - reference normalization + confidence-weighted candidate ranking
- Resolver API: `EntityResolver.attribute_outcome(references)` in `/Users/leoguinan/MetaSPN/metaspn-entities/metaspn_entities/resolver.py`
- Attribution tests in `/Users/leoguinan/MetaSPN/metaspn-entities/tests/test_attribution.py` covering:
  - merge after attempt, before outcome
  - undo-merge edge case
  - conflicting references with confidence tie-breaks

### Changed
- SQLite backend adds direct identifier lookup support for attribution scoring.
- Public exports now include `OutcomeAttribution`.

## 0.1.6 - 2026-02-06

### Added
- Recommendation-grade entity context model and builder in `/Users/leoguinan/MetaSPN/metaspn-entities/metaspn_entities/context.py`:
  - `RecommendationContext`
  - `build_recommendation_context(...)`
- Resolver API for recommendation workers:
  - `EntityResolver.recommendation_context(entity_id)`
- Tests for merged continuity, cross-source consistency, and rerun determinism:
  - `/Users/leoguinan/MetaSPN/metaspn-entities/tests/test_recommendation_context.py`

### Changed
- Public exports now include `RecommendationContext` and `build_recommendation_context`.
- Recommendation outputs are canonical redirect-safe and deterministic.

## 0.1.5 - 2026-02-06

### Added
- M1 entity context API for routing/profiling:
  - `EntityResolver.entity_context(entity_id, recent_limit=10)`
  - `EntityResolver.confidence_summary(entity_id)`
- New context model + deterministic rollup helper in `metaspn_entities.context`:
  - `EntityContext`
  - `build_confidence_summary(...)`
- Context-focused tests for cross-platform flows, merged continuity, and rerun stability in `tests/test_context.py`.

### Changed
- SQLite backend now exposes canonical identifier records with provenance and seen timestamps for context assembly.
- Public exports include `EntityContext` and `build_confidence_summary`.

## 0.1.4 - 2026-02-06

### Added
- M0 resolver pipeline adapter API in `metaspn_entities.adapter`:
  - `resolve_normalized_social_signal(resolver, signal_envelope, ...)`
  - `SignalResolutionResult` with `entity_id`, `confidence`, and emitted events.
- Adapter tests in `tests/test_adapter.py` for:
  - same author over multiple posts
  - cross-platform identifier normalization
  - idempotent rerun behavior
  - `metaspn-schemas` parseability of emitted events
- README worker/runtime invocation guidance for the M0 adapter.

### Changed
- Public package exports now include M0 adapter symbols in `metaspn_entities.__init__`.
- Package version bumped to `0.1.4`.

## 0.1.3 - 2026-02-06

### Added
- Event contract conformance tests for `EntityResolved`, `EntityMerged`, and `EntityAliasAdded` payloads.
- Optional round-trip compatibility tests against `metaspn-schemas` dataclasses when available.
- README note documenting event contract guarantees.

### Changed
- Resolver emissions now map to canonical `metaspn-schemas` entity payload shapes.
  - `EntityResolved`: `entity_id`, `resolver`, `resolved_at`, `confidence`, `schema_version`
  - `EntityMerged`: `entity_id`, `merged_from`, `merged_at`, `reason`, `schema_version`
  - `EntityAliasAdded`: `entity_id`, `alias`, `alias_type`, `added_at`, `schema_version`
- Merge emission semantics now correctly identify the resulting canonical entity and merged source IDs.

### Fixed
- Corrected auto-merge event payload mapping so `EntityMerged` fields are deterministic and schema-compatible.

## 0.1.2 - 2026-02-06
- Workflow rename to `publish.yml` for ecosystem consistency.

## 0.1.1 - 2026-02-06
- Packaging metadata fix for setuptools license expression compatibility.

## 0.1.0 - 2026-02-06
- Initial release.

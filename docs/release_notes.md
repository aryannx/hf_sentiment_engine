# Release Notes

## Unreleased
- Initial CI workflow added (`.github/workflows/ci.yml`) to run pytest on pushes/PRs.
- Data quality scaffold (lineage, validators, cross-source checks, position recon) integrated into fetchers.
- OMS/PMS/middle-office scaffolds and reporting scaffolds completed.
- Data pipeline orchestrator (`src/data_pipeline.py`) and cache admin CLI (`scripts/cache_admin.py`) added; validators can emit alerts; key rotation guidance documented.
- Release tagging workflow (`.github/workflows/release-tag.yml`) added; cache registry helper (`src/data/cache_registry.py`) for cache bookkeeping.

## 2025-12-05
- Consolidated docs and trackers; multi-ticker equities aggregator validated; credit OAS caching and CLI polish; compliance hooks added.


# Project Gaps (Lean View)

Focus on real-data deliverables; remove fluff.

## Data & Infra
- Done: Multi-provider fetch (Finnhub/FMP/FRED/Polygon, yfinance fallback), validators/lineage, logging/metrics/notifier/backup stubs, CI/release workflows, cache registry scaffold.
- Next: Promote `src/data_pipeline.py` to dual-mode (batch + intraday scheduler/loop with backoff); cache admin + lineage persisted (SQLite/Parquet); DQ alerts piped to notifier; enforced provider priority/quotas + key rotation note; nightly + intraday schedules documented.

## Equities
- Done: Dual-mode signals, sentiment overlay, credit/VIX overlays, benchmark/crisis metrics, multi-ticker aggregator with CSV/JSON/HTML/MD/zip, tests.
- Next: Crisis replay scripts packaged; standardized report packs (CSV/JSON/MD + ZIP) with templated summaries.

## Credit
- Done: HY/IG with FRED OAS percentile gating, IG/HY knobs, sentiment sizing, CLI backtester.
- Next: Trend/momentum ratio variant; richer CLI switches; more tests; improved FRED cache lifecycle (TTL, provenance).

## Volatility
- Done: VIX spot/futures fetch skeleton, term-structure metrics, signal/backtester stubs, tests.
- Next: Futures parser + contango/backwardation signals; hook signals into portfolio/risk; stress/MC suite.

## Intraday / HFT-lite
- Done: Polygon/Finnhub providers, rare/frequent/Crawford styles, cumulative delta gating, Alpaca paper log toggle, execution logger, tests.
- Next: Volume gating + FX/Alpaca symbols; breakout mode; live VWAP/microstructure feed; feature logging for copilot retrieval.

## OMS / Execution / TCA
- Done: Orders/routes/fills, sim with slippage/partials, TCA hooks, ADV/spread provider toggles, position ledger, audits.
- Next: Venue routing + broker attribution rollups; VWAP from intraday bars; Alpaca/FIX/IBKR bridge skeletons with heartbeat/test orders; impact/size curve + slippage bands.

## Middle Office / IBOR
- Done: Booking/recon/IBOR stubs, settlement scaffolds, break logging.
- Next: Corporate actions ingestion/applied to positions; cash recon automation; multi-custodian feeds; daily recon report with severities/buckets.

## PMS & Risk
- Done: Targets/drift/turnover/cash buffer, attribution/risk stubs, rebalance demo flag; risk limits/scenarios/VAR helpers.
- Next: Multi-portfolio configs (master/feeder, cash buffers, turnover caps); target-vol + correlation dashboards; margin/liquidity checks; pipe rebalance orders into OMS sim/bridges; enforce strategy/portfolio/firm limits (gross/net/notional/sector).

## Data Quality & Reconciliation
- Done: Lineage, staleness/schema/NaN/spike validators, cross-source checks, position recon tests.
- Next: Alerting/dashboard wiring; broader cross-source pairs (price/vol/volume); scheduled DQ runs; quarantine tagging on failures.

## Reporting & Compliance
- Done: Holdings/perf helpers, investor/reg templates, audit logging, CLI generator; compliance pre/post-trade scaffold.
- Next: Enrich templates with stress/attribution slots; approval metadata + access/approval logs; PDF binder packaging (offline only, no real filings).

## AI Research Copilot
- Done: Requirements captured.
- Next: Log-rich artifacts (signals/fills/breaks/DQ alerts/configs) to JSONL; embed code/docs/logs → vector store; minimal RAG CLI; audited tool runners (backtest/report fetch) with guardrails.

## Ops / Monitoring
- Done: Logging/metrics/notifier/backups/healthcheck stubs; runbook; release notes.
- Next: Uptime/latency probes per module; alert routes/on-call note; DR drill script; metrics sink (Prom/JSONL) + health probes.

## Release & CI
- Done: Pytest CI, release notes, release tag/build + smoke matrix workflows.
- Next: Keep release tagging + artifact publishing in use; extend smoke matrix as modules grow.


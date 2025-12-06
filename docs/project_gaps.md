# Project Gaps & Next Actions

Concise snapshot of what is done vs. what remains across the platform, with concrete next steps. Focused on real data (no synthetic generation) and production-minded scaffolds.

## Data & Infra
- Current: Multi-provider ingestion (Finnhub, FMP, FRED, Polygon, yfinance fallback), lineage logging, validators, runbook, DR checklist, backups, structured logging/metrics/alerts stubs.
- Gaps: Central scheduler/data_pipeline with cache registry and admin tooling; alert wiring for data-quality breaches; CI release tagging; secrets rotation automation.
- Next actions: Build `src/data_pipeline.py` orchestrator + cache admin CLI; add alert hooks from validators; publish release notes per sprint; codify key rotations.

## Equities
- Current: Dual-mode signals, sentiment blend, credit/VIX overlays, transaction costs, multi-ticker aggregator with reports; all equity tests passing.
- Gaps: Benchmark/60-40 overlays, crisis replays, standardized HTML/CSV packs.
- Next actions: Add benchmark loader + overlay metrics; script crisis replays; bundle report templates for interview/demo.

## Credit
- Current: HY/IG spread engine with FRED OAS, percentile gates, sentiment sizing hooks; execution sim optional.
- Gaps: Trend/momentum variant, richer CLI knobs, more tests; better FRED caching.
- Next actions: Add trend ratio strategy; expose percentile knobs cleanly; extend pytest coverage; improve cache lifecycle.

## Volatility
- Current: Scaffold only.
- Gaps: VIX futures parser, term-structure metrics, contango/backwardation signals, basic long/short strategy, stress/MCS hooks.
- Next actions: Implement VIX curve ingestion; add contango signals + simple strategy; wire into portfolio layer.

## Intraday / HFT-lite
- Current: Polygon/Finnhub adapters, RSI/Bollinger/Stoch signals (rare/frequent), backtester + CLI, tests.
- Gaps: Cumulative delta & volume gating, FX/Alpaca symbols, breakout mode, execution adapters.
- Next actions: Add delta/volume filters; extend symbol map to FX; prototype Alpaca paper route; log features for copilot retrieval.

## OMS / Execution / TCA
- Current: Orders/routes/fills models, execution simulator with slippage/partials, TCA pre/post hooks, ADV/spread provider toggles (static/Polygon/Finnhub), position ledger, CSV/JSON audits.
- Gaps: Venue routing, broker attribution time series, live VWAP from intraday bars, FIX/Alpaca/IBKR bridges, richer impact model.
- Next actions: Add venue selection + broker attribution rollups; compute VWAP from intraday bars by provider; prototype Alpaca paper adapter; design FIX/IBKR bridge interface.

## Middle Office / IBOR
- Current: Booking engine, settlement instruction stubs, recon engine (fund vs broker vs custodian), IBOR snapshots, break logging.
- Gaps: Corporate actions handling, cash recon automation, multi-custodian feeds, workflow for break resolution.
- Next actions: Add CA ingest hooks; implement cash recon; support multiple custodians; produce daily recon report with severities.

## Portfolio Management (PMS) & Risk
- Current: Portfolio/account models, targets, drift/turnover caps, cash buffer, rebalance proposals, basic attribution and risk stubs; risk engine with limits, scenarios/VAR, monitor loop.
- Gaps: Multi-portfolio/master-feeder configs, margin/liquidity waterfalls, correlation dashboards, target-vol scaling, OMS execution of rebalance orders.
- Next actions: Add portfolio configs + account routing; build correlation/target-vol module; integrate margin/liquidity checks; send rebalance orders through OMS sim.

## Data Quality & Reconciliation
- Current: Lineage logs, staleness/schema/NaN/spike validators, cross-source price checks, position recon vs broker CSVs; tests.
- Gaps: Dashboards/alerts, broader cross-source coverage, scheduled pipeline.
- Next actions: Emit validator alerts to notifier; expand cross-source pairs (Polygon vs Finnhub/yfinance); schedule nightly DQ runs.

## Reporting & Compliance
- Current: 13F-like holdings, performance summaries, investor/reg templates, audit logging for report generation; compliance pre/post-trade scaffold.
- Gaps: Richer templates (stress/attribution inserts), binder packaging, approval workflows; no real filings (offline only).
- Next actions: Flesh templates with stress/attribution slots; add approval metadata to outputs; package markdown → PDF binder scripts.

## AI Research Copilot
- Current: Requirements drafted (retrieval + LLM, CLI/Slack), no code yet.
- Gaps: Embedding pipeline, vector store, RAG service, tool execution with audit.
- Next actions: Ingest code/docs/logs into embeddings; stand up minimal RAG CLI; add safe tool runners (backtest, report fetch) with logging.

## Ops / Monitoring
- Current: Structured logging helper, healthcheck flags, metrics/heartbeat stubs, notifier hooks, backup script, DR checklist, runbook.
- Gaps: Real dashboards/alerts, uptime probes, on-call rotation artifacts, failover/DR drills.
- Next actions: Wire metrics to a sink (Prometheus-compatible); add uptime/latency probes; document on-call/alerts; script DR tabletop checklist.

## Release & CI
- Current: Pytest CI workflow, release notes file.
- Gaps: Automated versioning/tagging, artifact publishing, smoke matrices.
- Next actions: Add release tagging job; publish wheels/sdist internally; add quick smoke matrix (equity/credit/intraday).

## Summary
Platform has broad scaffolding (equities, credit, intraday, OMS/PMS, middle-office, risk, data quality, reporting, ops). Remaining work centers on volatility build-out, execution quality (venues/brokers/VWAP), AI copilot, scheduling/alerts, and richer portfolio/risk/DR automation—all on real data sources.


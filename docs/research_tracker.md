# Research Tracker (Deliverables-Only)

Date: Dec 6, 2025  
Scope: Concise status of what exists, what’s next, and where to focus. This replaces verbose status docs.

---

## Delivered (working today)
- **Equities**: Dual-mode mean reversion + sentiment, credit/VIX overlays, transaction costs, benchmark/crisis hooks in backtester; multi-ticker aggregator with CSV/JSON/HTML + markdown/zip outputs; tests for signals, backtester, aggregator, cumulative delta gating.
- **Credit**: HY/IG spread engine with FRED OAS percentile filter, IG/HY legs configurable, sentiment sizing, CLI backtester.
- **Intraday/HFT-lite**: Polygon/Finnhub providers (yfinance fallback), RSI/Bollinger/Stoch styles (rare/frequent/Crawford), cumulative delta gating, Alpaca paper log toggle, execution logger, CLI/backtester tests.
- **Volatility**: VIX spot/futures fetcher, term-structure metrics, basic signal generator, backtester skeleton; tests for signals/backtester.
- **OMS/MO/PMS**: Orders/fills/routing models, execution simulator with slippage/partials/TCA hooks, position ledger; middle-office booking/recon/IBOR stubs; PMS targets/drift/turnover/attribution/risk stubs; rebalance demo flag.
- **Risk**: Limit config/engine, scenarios/VAR helpers, margin stub, crisis windows; pre-flight risk hooks on runners.
- **Data Quality**: Lineage logging, staleness/schema/anomaly/NaN/spike validators, cross-source price checks, position recon vs broker CSVs; cache registry scaffold.
- **Reporting & Compliance**: 13F-like holdings/performance helpers, investor/reg templates, audit logger, CLI report generator; compliance pre/post-trade scaffold.
- **Ops/CI**: Structured logging/healthcheck/metrics/notifier/backups stubs, runbook, release notes, GitHub CI + release/tag/build + smoke-matrix workflows.

---

## In Flight / Next 2 Weeks
1) Intraday: tighten cumulative delta & volume gates; extend symbol map (FX/Alpaca).  
2) Volatility: finish VIX curve ingestion + contango/backwardation signals; wire to portfolio.  
3) AI Research Copilot: embeddings + vector store + minimal RAG CLI with audited tool runners (backtest/report fetch).  
4) Data pipeline: orchestrator + cache admin + DQ alert wiring.  
5) Portfolio/risk: target-vol + correlation dashboard; margin/liquidity hooks.  
6) Execution quality: live VWAP from intraday bars, venue routing weights, broker attribution rollups.

---

## Open Gaps (keep lean)
- **Volatility depth**: Futures parser, signal validation, crisis/MC stress.  
- **Execution**: FIX/IBKR bridge design, Alpaca paper routing polish, venue selection, impact model.  
- **Data quality**: Alert sinks/dashboards, broader cross-source coverage, scheduled DQ runs.  
- **AI copilot**: RAG service + CLI/Slack interface, audited tool execution.  
- **Portfolio**: Multi-portfolio configs, OMS handoff of rebalance orders, correlation/target-vol live.  
- **Ops/DR**: Uptime/latency probes, on-call rota, DR drill script.

---

## Quick Reference (where to look)
- Equities: `src/equities/*`, `src/main.py`, `src/equities/equity_aggregator.py`, `tests/test_equity_*`, `tests/test_intraday_delta.py`.
- Credit: `src/credit/credit_backtester.py`.
- Intraday: `src/intraday/*`, `tests/test_intraday_delta.py`.
- Volatility: `src/volatility/*`, `tests/test_volatility_*`.
- Execution/TCA: `src/exec/*`, `src/core/oms_*`, `src/core/position_ledger.py`.
- PMS/Risk: `src/pms/*`, `src/risk/*`.
- Data Quality: `src/data/*`, `scripts/cache_admin.py` (if present), `logs/cache_registry/`.
- Reporting/Compliance: `src/reporting/*`, `src/core/compliance_*`.
- Ops/CI: `.github/workflows/*.yml`, `docs/release_notes.md`, `docs/RUNBOOK.md`.

---

## Demo Commands (fast)
- Single equity: `python -m src.main --ticker AAPL --period 1y --mode position --credit_overlay --benchmark SPY --crisis_windows 2008_financial_crisis`
- Equity aggregator: `python src/equities/equity_aggregator_cli.py --top 10 --bundle_reports`
- Credit: `python -m src.credit.credit_backtester --period 1y --sent_thr 0.02 --z_window 30 --z_thr 0.5`
- Intraday (Crawford): `python -m src.intraday --ticker SPY --period 180d --interval 1h --provider polygon --style crawford --alpaca_paper_trade`
- Volatility smoke: `pytest tests/test_volatility_* -q`


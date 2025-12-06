# Modular Quant Platform

Multi-asset systematic research platform that mirrors an institutional hedge-fund workflow across equities, credit, and volatility. The system fuses technical signals, multi-source NLP sentiment, macro overlays, and portfolio construction so you can prototype strategies, run realistic backtests, and export production-ready signals.

## Executive Summary

- **Multi-asset coverage**: Equities, credit (HY/IG), volatility (VIX/ETNs), intraday/HFT-lite; real data only (Polygon/Finnhub/FMP/FRED/yfinance fallback, Alpaca-ready).
- **Cost- and risk-aware backtesting**: Event + position modes, transaction costs, benchmark/crisis overlays, credit/VIX throttles, PMS/risk hooks.
- **Execution/ops scaffolds**: OMS simulator with TCA hooks, middle-office booking/recon stubs, compliance checks, logging/metrics/healthchecks, cache registry.
- **Docs & CI**: Runbook, release notes, project gaps tracker, research tracker; GitHub Actions for CI, release tagging/builds, and smoke matrix.

The detailed intent, differentiators, and interview narrative live in [`docs/hf_drive_doc.pdf`](docs/hf_drive_doc.pdf). This README distills the execution plan and links to runnable components.

## Architecture at a Glance

```
┌─────────────────────────────┐
│ Data Ingestion Layer        │ FMP, Finnhub, FRED, yfinance, scrapers, caching
└───────────────┬─────────────┘
                ↓
┌─────────────────────────────┐
│ Signal Modules              │
│  • Equities: mean reversion + sentiment, dual modes
│  • Credit: HY-IG spreads, OAS percentiles, trend variant
│  • Volatility: VIX term-structure, vol-of-vol, macro overlays
│  • Intraday: 1h/5m Bollinger + RSI/Stochastic mean reversion, microstructure hooks
└───────────────┬─────────────┘
                ↓
┌─────────────────────────────┐
│ Portfolio & Risk Layer      │
│  • Static/dynamic weights   │
│  • Credit/VIX risk throttles│
│  • Target-vol scaling       │
│  • Correlation analytics    │
└───────────────┬─────────────┘
                ↓
┌─────────────────────────────┐
│ Backtesting & Reporting     │
│  • Event & position runners │
│  • Transaction costs        │
│  • Walk-forward / OOS       │
│  • Monte Carlo envelopes    │
│  • Signal export + dashboard│
└─────────────────────────────┘
```

## Technology Stack

| Domain              | Tools                                                                 |
| ------------------- | --------------------------------------------------------------------- |
| Core language       | Python 3.9+, `pandas`, `numpy`, `pydantic` (planned)                   |
| Technical analysis  | `TA-Lib`, `pandas-ta`, in-house indicators                            |
| Sentiment / NLP     | `nltk` (VADER), `textblob`, custom keyword filters                    |
| Data sources        | Polygon (primary intraday/equity), Finnhub (secondary), FRED (credit), yfinance (fallback) |
| Backtesting         | Custom engines in `src/equities`, `src/credit`, `src/volatility`      |
| Visualization       | `matplotlib`, `seaborn`, `plotly`, Streamlit dashboard (`app/`)       |
| Storage             | SQLite/pickle caches (planned), CSV/JSON signal export                |
| Tooling             | `pytest`, `black`, `ruff` (optional), Git, virtualenv                 |

## Repository Layout

```
hf_sentiment_engine/
├── app/                     # Streamlit dashboard shell
├── docs/                    # Design docs, runbooks, PDFs
├── src/
│   ├── equities/            # Data fetchers, sentiment, signals, backtester
│   ├── credit/              # HY/IG spread engines, sentiment overlays
│   ├── volatility/          # VIX + vol module (WIP)
│   ├── intraday/            # Day-trader module (multi-provider data, signals, CLI)
│   ├── core/                # Shared signal helpers, base classes
│   └── utils/               # Metrics, validators, export hooks
├── tests/                   # pytest suites (placeholders to be expanded)
├── requirements.txt
├── .env.example             # Environment variable template
└── README.md
```

## Getting Started

1. **Clone & install**
   ```bash
   git clone https://github.com/aryannx/hf_sentiment_engine.git
   cd hf_sentiment_engine
   python -m venv .venv && .\.venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. **Environment variables**
   ```bash
   copy env.example .env  # or cp on macOS/Linux
   # populate API keys per the table below
   ```
3. **Optional native deps**
   - TA-Lib: install system binaries (`brew install ta-lib` or `choco install ta-lib`), then `pip install TA-Lib`.
   - `curl_cffi` for more reliable yfinance sessions.

## Required API Keys

| Variable             | Purpose                                    | Notes                          |
| -------------------- | ------------------------------------------ | ------------------------------ |
| `FINNHUB_API_KEY`    | Price/news/sentiment for equities/credit   | $30/mo starter tier            |
| `FMP_API_KEY`        | News, fundamentals, macro feeds            | $30/mo                        |
| `FRED_API_KEY`       | Macro series (HY OAS, rates)               | Free                           |
| `EODHD_API_KEY`      | Supplemental news stream                   | Optional                       |
| `POLYGON_API_KEY`    | Intraday bars for HFT-lite module          | Optional                       |
| `ALPACA_API_KEY/SECRET` | Intraday prototype execution data      | Optional                       |

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for caching, rotation, and failover guidance.

## Running Pipelines

Equity pipeline (single ticker, sentiment overlay, optional credit risk):
```bash
python -m src.main --ticker AAPL --period 1y --mode position --credit_overlay
```

Equity backtester variants (uses Polygon→Finnhub→yfinance priority):
```bash
python -m src.equities.equity_backtester \
  --ticker MSFT \
  --style conservative \
  --mode position \
  --cost_bps 5 \
  --split 0.7 --validate_oos
```

Credit spread engine with OAS filter (once finalized):
```bash
python -m src.credit.credit_backtester \
  --period 3y \
  --sent_thr 0.05 \
  --z_window 60 \
  --z_thr 1.0 \
  --use_percentile \
  --lower_pct 10 --upper_pct 90
```

Intraday mean-reversion runner (RSI/Stochastic/Bollinger stack):
```bash
python -m src.intraday \
  --ticker ES=F \
  --period 180d \
  --interval 1h \
  --provider polygon \
  --style rare \
  --confirmations volume,divergence \
  --support_levels 4800,4750
```

### Multi-Ticker Equity Aggregator

Run comprehensive portfolio analysis across multiple tickers with parallel processing and automated reporting:

```bash
# Analyze top 20 tickers
python src/equities/equity_aggregator_cli.py --top 20

# Analyze specific tickers
python src/equities/equity_aggregator_cli.py --tickers AAPL MSFT GOOGL TSLA NVDA

# Load from watchlist file
python src/equities/equity_aggregator_cli.py --watchlist my_portfolio.txt --credit-overlay

# Custom analysis with OOS validation
python src/equities/equity_aggregator_cli.py --top 10 --period 2y --validate-oos --cost-bps 10
```

**Outputs:**
- **CSV**: Tabular results for analysis
- **JSON**: Structured data with metadata
- **HTML**: Interactive report with performance tables

All commands emit CSV/JSON/HTML reports in `reports/` (or custom `--output` directory). Use the Streamlit app for visual drill-down once `app/dashboard.py` is wired.

## Compliance (Pre/Post-Trade Scaffolding)

- **Engine:** `src/core/compliance_engine.py` with configurable limits (`max_positions`, `max_single_name_pct`, `max_gross_notional`, leverage, turnover placeholders).
- **Rules:** defaults live in `src/core/compliance_rules.py` (pass/warn/block with audit-friendly messages).
- **Audit:** JSONL logs in `logs/compliance/` (gitignored) for pre/post-trade checks.
- **Equities:** `src/main.py` and `src/equities/equity_aggregator_cli.py` run pre-trade checks on proposed tickers (equal-weight assumption); blocks halt runs, warnings are surfaced.
- **Credit:** `src/credit/credit_backtester.py` checks IG/HY legs before backtest; post-trade stub records results after backtest.
- **Extending:** swap limits via constructor or future config file; ready for OMS/FIX adapters and richer rule sets (sector/issuer/mandate).

## OMS / Execution Simulation (Scaffold)

- **Domain models:** Orders, fills, routes in `src/core/oms_models.py`; execution config in `src/core/oms_config.py`.
- **Simulator:** `src/core/oms_simulator.py` applies slippage/partial fills, logs to `logs/oms/`.
- **Ledger:** `src/core/position_ledger.py` tracks cash/positions/realized PnL using marks.
- **Integration:** `src/main.py` (equities) and `src/credit/credit_backtester.py` can run with `simulate_execution=True` to consume fills instead of idealized fills; current sizing is simple and can be extended.
- **Reports:** Order/fill audits go to JSONL; TCA hooks ready for extension. Next: broker/FIX adapters and richer allocation/sizing + full TCA.

## PMS (Portfolio Management Scaffold)

- **Models/Config:** `src/pms/models.py`, `src/pms/config.py` (portfolio/account, targets, drift/turnover caps, cash buffer).
- **Rebalancer:** `src/pms/rebalancer.py` computes drift vs targets, turnover cap, cash buffer; outputs rebalance orders.
- **Attribution:** `src/pms/attribution.py` for simple contribution/benchmark excess (factor stubs later).
- **Risk:** `src/pms/risk.py` gross/net exposure, leverage, stress bump placeholder.
- **Hook:** `src/main.py` demo flag `pms_rebalance=True` prints a rebalance proposal using demo config.
- **Next:** multi-portfolio configs, account-level allocation, richer margin models, and piping rebalance orders into OMS sim for execution.

## Data Quality & Reconciliation (Scaffold)

- **Lineage:** `src/data/lineage.py` logs source/timestamp/checksum to `logs/data_lineage/`.
- **Validators:** `src/data/validators.py` for staleness, schema, NaN, and spike checks.
- **Cross-source:** `src/data/cross_source.py` compares primary vs secondary prices with tolerance.
- **Integration:** Equity and credit fetchers run validators and log lineage on download.
- **Position recon:** `src/data/position_recon.py` compares fund positions to broker/custodian CSVs (leverages middle-office recon).
- **Tests:** `tests/test_data_validators.py`, `tests/test_position_recon.py`.

- **Structured logs & healthchecks:** JSON logs helper in `src/core/logging_utils.py`; `--healthcheck` flags on equity/credit/intraday CLIs for probes.
- **Metrics/heartbeat:** `src/core/metrics.py` writes counters/timers to `logs/metrics/` when `METRICS_ENABLED=1`.
- **Alerts:** `src/core/notifier.py` logs alerts to `logs/alerts/` and optionally posts to `ALERT_WEBHOOK_URL`.
- **Backups:** `scripts/backup.sh` snapshots `logs`, `reports`, and `data` to `backups/<timestamp>/`.
- **Runbook:** Operational details live in `docs/RUNBOOK.md`; DR/checklist content consolidated there.

## Risk Management & Limits (New)

- **Config & limits:** `src/risk/config.py` defines strategy/portfolio/firm limits (max position %, gross/net leverage, sector caps, concentration, liquidity buffer) plus stress shocks and VAR alpha.
- **Engine:** `src/risk/engine.py` computes exposures (gross/net/beta) and evaluates limits with block/warn severities; uses `risk.models.Position`.
- **Scenarios/VAR:** `src/risk/scenario.py` offers simple shocks and historical/parametric VAR helpers. Margin/ liquidity stubs in `src/risk/margin.py`.
- **Integrations:** Equity runner, credit backtester, intraday CLI, and aggregator CLI optionally perform pre-flight risk checks (see flags). Alerts/metrics tie into existing logging/metrics/notifier.
- **Next:** richer real-time risk, correlation tracking, margin waterfalls, and volatility module integration.

## Regulatory & Investor Reporting (Scaffold)

- **Holdings/Perf helpers:** `src/reporting/holdings.py` (13F-like snapshot, top holdings) and `src/reporting/performance.py` (perf summary: return, Sharpe, Sortino, max DD, monthly returns).
- **Templates:** `docs/templates/investor_letter.md`, `docs/templates/regulatory_summary.md` (filled into Markdown outputs).
- **Audit:** `src/reporting/audit.py` logs generation/approvals to `logs/reporting/` (JSONL).
- **CLI:** `src/reporting/generate_reports.py` takes positions/equity CSVs and emits Markdown + CSV/JSON to `reports/investor/` and `reports/regulatory/`.
- **Note:** Offline only—no real EDGAR/MiFID submissions; placeholders to show workflow readiness.

## Nightly Batch & Caching Workflow

1. Kick off `python -m src.data_pipeline` (planned) or `src/main.py` watchlists after market close.
2. Fetch & cache data per ticker/source with staleness checks (24h default).
3. Generate signals for each module, apply transaction costs, risk overlays.
4. Run walk-forward validation + Monte Carlo envelope (once implemented).
5. Export signals/analytics to `reports/` and optionally notify via email/webhook.

Operational specifics (logging, retries, rollout) are documented in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Testing & QA

- Unit tests now cover equity/intraday signal math, data fetcher indicator sanity, sentiment blending, and trade-level P&L reconciliation.
- Integration tests (in-progress) will mock API responses to exercise fetch → signal → backtest pipelines.
- Forthcoming stress suites will replay 2008/2020 crises and compare to SPY / 60-40 portfolios.

Run locally with:
```bash
pytest -q
```

## Roadmap

- ✅ Architecture, equity sentiment pipeline, dual-mode backtesting, intraday scalper module (multi-provider), credit skeleton
- 🚧 Current focus: documentation, multi-ticker equity runner, credit OAS filter, volatility module MVP, portfolio allocator, Streamlit dashboards, CI & tests
- 🔜 Medium term: Monte Carlo envelopes, benchmark dashboards, AI research copilot (chatbot over local notebooks/logs), Bloomberg-style terminal adapter + execution bridges (IBKR/Bloomberg), asset-class expansion into options/derivatives, fixed income, and commodities

## Intraday Strategy (Quick talking points)

- **Goal:** HFT-lite mean-reversion watcher on 1h/5m bars; fires only on extreme RSI/Bollinger/Stoch alignments (rare/frequent/Crawford styles).
- **Data:** Polygon/Finnhub (yfinance fallback), Alpaca-ready logging; indicators engineered uniformly per provider.
- **Risk/discipline:** Transaction costs, max-hold windows, delta/volume gating; logs every candidate for auditability.
- **Scale path:** Add FX coverage, breakout mode, live VWAP/venue routing, and AI copilot queries over logged events.


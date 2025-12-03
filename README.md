# Modular Quant Platform

Multi-asset systematic research platform that mirrors an institutional hedge-fund workflow across equities, credit, and volatility. The system fuses technical signals, multi-source NLP sentiment, macro overlays, and portfolio construction so you can prototype strategies, run realistic backtests, and export production-ready signals.

## Executive Summary

- **Asset coverage** – Equities (single names & portfolios), credit (HY vs. IG spreads), volatility (VIX & ETNs), plus a new intraday/HFT-lite module for high-conviction mean-reversion scalps fed by institutional APIs (Finnhub, Polygon, Alpaca).
- **Dual-mode backtesting** – Event-driven (+1/0/-1 bars) for fast sweeps and position-mode for true P&L with exits, transaction costs, and risk overlays.
- **Alternative data integration** – Finnhub, Financial Modeling Prep, custom scrapers, and sentiment blending with VADER/TextBlob plus credit-specific lexicons.
- **Risk-aware portfolio layer** – Dynamic position sizing off credit spreads & VIX, target-vol scaling, strategy correlations, and exportable analytics.
- **Production-minded design** – Modular `src/` packages, CLI entry points, SQLite/pickle caching, logging hooks, CI-ready tests, and Streamlit dashboards.

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
| Data sources        | Finnhub, Financial Modeling Prep, FRED, Polygon, Alpaca, yfinance (fallback) |
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
│   ├── portfolio_manager.py # Multi-strategy allocator (WIP)
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

Equity backtester variants:
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

Portfolio allocator (WIP, target-vol sizing placeholder):
```bash
python -m src.portfolio_manager \
  --strategies equities credit volatility \
  --target_vol 0.10 \
  --risk_rules configs/portfolio.yaml
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

All commands emit CSV/JSON reports in `reports/` (or `results/` once added). Use the Streamlit app for visual drill-down once `app/dashboard.py` is wired.

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

## Intraday Strategy Narrative (Interview Cheat Sheet)

When explaining the intraday/HFT-lite module to funds or interviewers:

- **Why it exists** – “I wanted a scalper strategy that never sleeps. It watches 1h/5m bars and only fires when price, RSI, and stochastic all scream ‘mean reversion’—exactly the kind of rare setup humans often miss.”
- **Signal recipe** – RSI ≤16 (or ≥84) + price ≥2.5σ beyond Bollinger bands + slow stochastic cross. Optional confirmations for volume spikes, RSI divergence, or proximity to predefined support/resistance. Built-in regime detection so it only trades sideways markets unless a breakout flag is set.
- **Data quality** – Pulls bars from Finnhub and Polygon (with yfinance fallback), meaning it can easily pivot to brokerage-grade data (Alpaca/IBKR) for execution. Indicators are engineered uniformly regardless of provider.
- **Risk framing** – Scarce setups ⇒ low trade count but high win rate. Backtests enforce transaction costs, max-hold windows, and log every candidate event (even the ones filtered out) so PMs can audit scarcity vs discipline.
- **Scalability** – The module already supports equities/futures/FX. Next steps include cumulative delta gating, options/fixed-income/commodities overlays, and an AI research copilot that can answer “show me every RSI≤12 signal in 2025 and how volume behaved.”
- **Demo commands** – Showcase with:  
  ```bash
  python -m src.intraday --ticker ES=F --period 180d --interval 1h --provider polygon --style rare --confirmations volume,divergence --support_levels 4800,4750
  ```
  Mention that results export to JSON/CSV and can feed dashboards or execution adapters.

Use this story to demonstrate short-horizon expertise, disciplined signal design, and a roadmap toward professional-grade execution and AI-assisted research.


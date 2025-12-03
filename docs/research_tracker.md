# Modular Quant Platform – Master Tracker & Roadmap

**Date:** December 3, 2025 (Updated: December 3, 2025)  
**Owner:** Aryan Nambiar  
**Purpose:** Exhaustive tracker for everything we have built or promised across equities, credit, volatility, intraday, portfolio, AI copilot, execution, and documentation. This replaces all previous status docs.

---

## 0. Recent Progress (Last Session)

✅ **Completed:**
- Project rebranded from "HF Sentiment Engine" → "Modular Quant Platform" across all documentation
- Equities module fully tested: **9/9 tests passing** (`test_equity_backtester`, `test_equity_data_fetcher`, `test_equity_sentiment_analyzer`, `test_equity_signals`)
- Fixed signal generator test expectations to match actual event/position mode behavior
- All documentation updates committed and pushed to GitHub (`main` branch)
- Consolidated status reports into single `research_tracker.md`

🎯 **Next Immediate Steps:**
1. Equities multi-ticker aggregator & reporting (batch run top 20 tickers, heatmaps)
2. Credit OAS CLI polish + FRED cache implementation
3. Intraday delta/volume gating enhancements
4. GitHub CI workflow setup (PAT/SSH configuration)

---

## 1. Executive Overview

| Pillar | Status | What Exists | What’s Coming |
| --- | --- | --- | --- |
| **Data & Infra** | ✅ | Finnhub/FMP/FRED/Polygon/yfinance ingestion, caching plan, runbook, README | Unified `data_pipeline`, cache registry, structured logging, release notes |
| **Equities** | ✅ | Dual-mode mean reversion + sentiment, credit/VIX overlays, watchlist CLI, cost-aware backtester | Multi-ticker aggregation, automated OOS metrics, benchmark overlays, crisis stress tests |
| **Credit** | 🟡 | HY–IG spread engine with OAS percentile gates & sentiment sizing | Import cleanup, FRED cache, trend/momentum variant, CLI polish |
| **Volatility** | 🟠 | Scaffolding in `src/volatility/` | VIX futures parser, contango/backwardation signals, Monte Carlo + stress testing |
| **Intraday / HFT-lite** | ✅ | Finnhub/Polygon data adapters, RSI/Bollinger/Stoch signal styles, CLI, backtester, pytest coverage | Cumulative delta/volume gating, FX + Alpaca support, breakout mode experiments |
| **Portfolio & Risk** | 🟡 | Kelly-style stub, aggregator placeholder | Covariance-aware target-vol scaling, correlation dashboards, strategy gating |
| **AI Research Copilot** | 🟠 | Requirements drafted (retrieval + LLM) | Embedding pipeline, vector DB, CLI/Slack hooks, tool execution |
| **Execution & Ops** | 🟠 | Runbook, README, remote reset, tests ready | GitHub Actions relaunch, Alpaca paper adapter, IBKR/Bloomberg bridge |

---

## 2. Data & Tooling Backbone
- **APIs:** Finnhub (prices/news/sentiment), FMP (news/fundamentals), FRED (macro/OAS), Polygon (intraday), Alpaca (planned execution), yfinance (fallback), EODHD (aux sentiment).
- **Environment:** `.venv` (Py3.11) with pinned requirements; `setup_nlp.py` for VADER/TextBlob downloads.
- **Ops artifacts:** Runbook, README, nightly schedule, caching policy, logging guidance.
- **Planned infra upgrades:** central `src/data_pipeline.py`, cache registry + admin script, structured JSON logging, Slack/email alerts, release notes file.

---

## 3. Module Deep Dive

### 3.1 Equities (Mean Reversion + Sentiment)
- **Pipeline:** Fetch OHLCV → blend sentiment (Finnhub/FMP/EODHD) → generate event/position signals → apply credit/VIX risk overlays → backtest with transaction costs.
- **CLI:** `python -m src.main` with watchlists, multi-ticker runs, CSV/JSON exports, transaction cost + split flags.
- **Tests:** ✅ **All 9 tests passing** — `tests/test_equity_*` covering fetchers, sentiment analyzer, signal generator (event & position modes), backtester math, OOS splits, transaction costs.
- **Backlog:** Multi-ticker aggregator/heatmap, automatic benchmark overlay (SPY/60-40), crisis replay scripts, standardized report outputs.

### 3.2 Credit (HY vs IG)
- **Features:** Aligns LQD/HYG, fetches HY OAS from FRED, trades by percentile regimes, sentiment sizing hooks.
- **To-Do:** Clean imports, cache OAS data, expose CLI percentile knobs, add trend-following ratio strategy, expand pytest coverage.

### 3.3 Volatility
- **Current:** Structural files only.
- **Future:** VIX futures parser → contango/backwardation metrics, simple long/short vol strategy, integration with portfolio manager, Monte Carlo + crisis tests.

### 3.4 Intraday / Day-Trader Module
- **Goal:** “Algo that never sleeps” – monitors 1h/5m bars for RSI/Bollinger/Stoch extremes across equities/futures/FX.
- **Providers:** Finnhub/Polygon (API keys) with yfinance fallback; planned Alpaca execution.
- **Signal styles:** `rare` (RSI ≤16/≥84, ≥2.5σ, slow stochastic) vs `frequent` (RSI ≤20/≥80, ≥1.2σ, fast stochastic) with optional confirmations (volume spike, RSI divergence, support proximity) and regime filters.
- **Backtesting:** Entry on signal close, exit at Bollinger midline/max hold, transaction-cost deductions, trade metadata logged.
- **Tests:** `pytest tests/test_intraday_signals.py`.
- **Next:** Add cumulative delta + volume gating, extend CLI to FX symbols, feed logs to AI copilot, implement breakout mode, hook into Alpaca/IBKR.

### 3.5 Portfolio & Risk
- **Now:** Kelly-style weights.
- **Next:** Rolling covariance matrix, target-vol scaling, correlation dashboards, marginal contribution analysis, risk gating based on credit/vol signals.

### 3.6 AI Research Copilot
- **Vision:** Repo-wide assistant answering “Why did ES trade?” or “Summarize last night’s credit OAS run.”
- **Implementation plan:** Embedding pipeline + vector DB → retrieval-augmented LLM service (OpenAI/Anthropic), CLI/Slack interfaces, and safe tool execution (rerun backtests, fetch logs) with audit.

### 3.7 Execution Bridges
- **Short-term:** Alpaca paper adapter.
- **Mid-term:** IBKR API (TWS) integration, slippage logging.
- **Long-term:** Bloomberg EMSX / blpapi adapter and terminal-style command suite.

---

## 4. Roadmap

### Immediate (1–2 Weeks)
1. Re-enable GitHub CI (PAT/SSH) + lint/test workflow.  
2. Intraday delta/volume gating + FX/Alpaca symbols.  
3. Equities multi-ticker aggregation & reporting.  
4. Credit OAS CLI polish + FRED cache.  
5. AI copilot skeleton (embeddings + retrieval).  
6. Data pipeline scaffolding + cache admin script.

### Near-Term (1–2 Months)
1. Volatility MVP (VIX parser + strategy).  
2. Portfolio target-vol scaling + correlation dashboard.  
3. Benchmark + Monte Carlo tooling.  
4. Alpaca paper execution prototype.  
5. AI copilot beta (CLI + Slack bot with citations).

### Medium-Term (Quarter)
1. Asset-class expansion (options/derivatives, fixed income, commodities).  
2. Intraday breakout-mode validation.  
3. Execution bridges (IBKR/Bloomberg).  
4. Automated nightly scheduler + alerting.  
5. AI copilot tool execution.

---

## 5. Task Matrix

| Area | Task | Status |
| --- | --- | --- |
| Documentation | Project rebranding & tracker consolidation | ✅ Complete |
| Equities | Test suite (all 9 tests passing) | ✅ Complete |
| Equities | Multi-ticker aggregator & heatmap | 🔄 In Progress (Next) |
| Equities | Benchmark overlay & crisis scripts | Planned |
| Credit | CLI cleanup, FRED cache, trend variant | 🔄 Next Priority |
| Volatility | VIX parser + contango strategy | Planned |
| Intraday | Delta/volume gating, FX support, breakout mode | Planned |
| Portfolio | Covariance + target-vol engine | Planned |
| AI Copilot | Embedding + retrieval service | Planned |
| Execution | Alpaca paper adapter, IBKR/Bloomberg bridge | Planned |
| Ops | Re-enable CI, add release notes | 🔄 Next Priority |

---

## 6. Interview & Demo Talking Points
- Intraday rarity narrative (“algo never sleeps”) with demo command.  
- Cross-asset overlays (credit/VIX) throttling equities.  
- Ops discipline (runbook, caching, logging, pytest).  
- AI copilot vision (repo-wide retrieval + actions).  
- Execution roadmap (Alpaca now, IBKR/Bloomberg next).

---

## 7. Action Items

### Tier 1 – Immediate (This Week)
| Owner | Action | Status |
| --- | --- | --- |
| Aryan | ✅ Project rebrand & documentation consolidation | Complete |
| Aryan | ✅ Equities module test suite verification | Complete |
| Aryan | 🔄 Multi-ticker equity aggregator + reporting | In Progress |
| Aryan | 🔄 Credit OAS CLI polish + FRED cache | Next |
| Aryan | 🔄 Re-enable GitHub CI (PAT/SSH setup) | Next |

### Tier 2 – Near-Term (1–2 Weeks)
| Owner | Action | Target |
| --- | --- | --- |
| Aryan | Intraday delta/volume gating + FX support | Mid Dec |
| Aryan | Build AI copilot MVP (embeddings + retrieval) | Mid Dec |
| TBD | VIX parser & strategy | Late Dec |
| TBD | Portfolio target-vol engine | Late Dec |

### Tier 3 – Medium-Term (1–2 Months)
| Owner | Action | Target |
| --- | --- | --- |
| TBD | Alpaca paper execution adapter | Early Jan |
| TBD | Execution bridges (IBKR/Bloomberg) | Q1 2026 |

---

**Current Status:** ✅ Platform MVP (equities + credit skeleton + intraday) is functional and documented. Focus now: delta filters, multi-asset expansion (vol/options/fixed income/commodities), AI copilot service, and professional execution bridges so the Modular Quant Platform mirrors real hedge-fund workflows end-to-end.


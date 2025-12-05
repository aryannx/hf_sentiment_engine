# Modular Quant Platform – Operations Runbook

> Living document for nightly research runs, data hygiene, and incident response. Update alongside code changes.

## 1. Environments & Secrets

- **Virtual env**: `.venv` (local) or `/opt/hf_sentiment_engine/.venv` (server). Recreate after dependency bumps.
- **Config files**:
  - `env.example` → copy to `.env` for local dev.
  - `config/portfolio.yaml` (future) drives allocator weights and risk limits.
- **Secrets management**:
  - Local: `.env` (gitignored) sourced automatically by `python-dotenv`.
  - CI/deploy: Use OS-level secure store or GitHub Actions secrets.
  - Rotate Finnhub/FMP keys quarterly or if you trigger >80% usage.

| Var | Description | Rotation |
| --- | ----------- | -------- |
| `FINNHUB_API_KEY` | Primary price/news/sentiment | 90 days / on leak |
| `FMP_API_KEY`     | Fundamentals + news           | 90 days |
| `FRED_API_KEY`    | Macro data                    | Annual |
| `POLYGON_API_KEY` | Intraday bars (intraday module) | Monthly usage review |

## 2. Nightly Batch Schedule (UTC-5)

| Time  | Job | Command |
| ----- | --- | ------- |
| 16:10 | Warm cache / health check | `python scripts/ping_sources.py` (planned) |
| 16:15 | Equity universe | `python -m src.main --watchlist configs/universes/core_equities.yaml --mode position --credit_overlay` |
| 16:45 | Credit spreads | `python -m src.credit.credit_backtester --period 3y --use_percentile --lower_pct 10 --upper_pct 90` |
| 17:05 | Volatility module | `python -m src.volatility.volatility_backtester --period 2y --term_structure contango` |
| 17:20 | Portfolio aggregation | `python -m src.portfolio_manager --strategies equities credit volatility --target_vol 0.10` |
| 17:35 | Reporting & export | `python scripts/export_reports.py --format csv,json,html` |

Each job logs to `logs/signal_engine.log` (rolling 20 MB) with `INFO` baseline.

## 3. Data Caching & Staleness

- Cache root: `data/cache/` (configurable via `CACHE_ROOT`).
- Structure: `{provider}/{symbol}/{date}.parquet` plus SQLite metadata in `cache.db`.
- Before each fetch:
  1. Check metadata table for `{provider, symbol, start, end}` and `updated_at`.
  2. If <24h old, reuse cached file (unless `--force_refresh` flag is supplied).
- After fetch:
  - Persist raw JSON/CSV.
  - Append ingestion log entry for auditing (`logs/ingestion.log`).
- Emergency purge:
  ```bash
  python scripts/cache_admin.py --purge --provider finnhub --symbol AAPL
  ```

## 4. Error Handling & Retries

- **HTTP 429/5xx**:
  - Exponential backoff (1s, 2s, 4s, 8s, 16s) up to 5 attempts.
  - After final failure, emit `WARN` and fallback to cached data; mark run as `DEGRADED`.
- **Data validation failures** (NaNs, misaligned timestamps):
  - Logged as `ERROR`.
  - Offending ticker recorded in `reports/run_status.json`.
  - Pipeline skips downstream steps for that ticker but continues others.
- **Unexpected exceptions**:
  - Logs stack trace.
  - Sends notification hook (Slack/email placeholder in `scripts/notify.py`).

## 5. Manual Run Procedure

1. Activate environment, ensure `git status` clean.
2. Pull latest main, review `hf.plan.md` and `docs/RUNBOOK.md` for updates.
3. Dry-run equity module on a single ticker:
   ```bash
   python -m src.main --ticker AAPL --period 6mo --mode event --dry_run
   ```
4. If healthy, launch watchlist run (see schedule).
5. Verify outputs:
   - `reports/backtests/*.csv`
   - `reports/metrics/*.json`
   - Streamlit dashboard caches.
6. Commit generated artifacts only if explicitly required (usually keep in `/reports` for inspection but out of Git unless sanitized).

## 6. OOS Validation & Monitoring

- Weekly, run walk-forward split for each flagship ticker/universe:
  ```bash
  python -m src.equities.equity_backtester --ticker SPY --split 0.7 --validate_oos
  ```
- Record training vs. OOS Sharpe/MaxDD deltas in `reports/oos_registry.csv`.
- Flag pipelines where OOS Sharpe drops >20% versus training set.

## 7. Testing & Release Checklist

Before merging to `main` or cutting a release:

- [ ] `pytest -q`
- [ ] `ruff check src/ tests/` (optional)
- [ ] `black --check src/ tests/`
- [ ] Manual smoke test on representative ticker per module (AAPL / HYG / SVXY).
- [ ] Update `README.md` and this runbook if workflows changed.
- [ ] Ensure `env.example` includes any new configuration knobs.

## 8. Incident Playbooks

| Symptom | Action |
| ------- | ------ |
| Repeated API 429 | Swap to cached data, contact provider to lift limits, consider reducing watchlist size. |
| Missing credit OAS data | Verify FRED API key, fall back to price-based spread proxy with `--disable_oas`. |
| Stale sentiment values | Recompute using local NLP fallback (`python scripts/offline_sentiment.py`). |
| Portfolio volatility > target | Auto-scale notional via `portfolio_manager`, log override reason, rerun allocation. |

## 9. Healthchecks & Metrics (Scaffold)

- Health probes: `python -m src.main --healthcheck`, `python -m src.credit.credit_backtester --healthcheck`, `python -m src.intraday --healthcheck`.
- Metrics/heartbeat files: `logs/metrics/metrics_*.jsonl` when `METRICS_ENABLED=1` is set.
- Alerts: written to `logs/alerts/alerts_*.jsonl`; optional webhook via `ALERT_WEBHOOK_URL`.

## 10. Backup / DR (Scaffold)

- Ad-hoc snapshot: `bash scripts/backup.sh` (archives `logs`, `reports`, `data/raw`, `data/cache` into `backups/<timestamp>/`).
- Verify backups: `ls backups/` and inspect latest tarballs.
- On-call checklist: see `docs/dr_checklist.md` for step-by-step probes and incident logging.

---

Document owner: Aryan Nambiar • Last updated: December 3, 2025. Update immediately when workflow changes.


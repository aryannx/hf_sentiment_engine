# Risk Framework – Actionable Build Note

## Components
- Config & limits: `src/risk/config.py` (strategy/portfolio/firm limits, sector caps, liquidity buffer, correlation threshold, stress shocks, VAR alpha).
- Engine: `src/risk/engine.py` (gross/net/beta exposures, limit evaluation, factor exposure, correlation flags, Greek aggregation).
- Factors: `src/risk/factors.py` (factor exposures, high-correlation detection).
- Scenarios/VAR: `src/risk/scenario.py` (shock runner, crisis presets, historical/parametric VAR).
- Margin/Liquidity: `src/risk/margin.py` (haircut-based requirement, leverage ratio).
- Greeks: `src/risk/greeks.py` (placeholder aggregator).
- Monitoring: `src/risk/monitor.py` (snapshot loader, evaluate loop, notifier/metrics hooks).

## How to Run
- Equity pipeline (pre-flight risk): `python -m src.main --ticker AAPL`
- Credit backtest: `python -m src.credit.credit_backtester --period 1y`
- Intraday runner: `python -m src.intraday --ticker ES=F --interval 1h`
- Equity aggregator with risk check: `python src/equities/equity_aggregator_cli.py --top 5 --risk-check --risk-nav 100000`
- Monitoring loop (snapshot JSON/CSV with ticker/qty/price/sector/beta): use `RiskMonitor().loop(Path("positions.json"), interval_seconds=60, iterations=1)`

## Crisis / VAR
- Crisis shocks: `apply_crisis_scenarios(positions)`; custom shocks via `run_scenarios`.
- VAR helpers: `parametric_var(returns, alpha)` or `historical_var(returns, alpha)`.

## Next Steps
- Add live data feeds for positions/PNL, integrate volatility module and options books.
- Add factor model inputs (beta maps) and correlation dashboards.
- Add margin call logic and liquidation waterfall; broker/PB-specific haircuts.
- Move monitoring to a service with alert routing (Slack/PagerDuty) and dashboards.


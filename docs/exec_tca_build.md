# Execution Quality & TCA – Actionable Build Note

## Components
- Config/models: `src/exec/config.py`, `src/exec/models.py`.
- Pre-trade: `src/exec/pretrade.py` (slippage/impact estimate, strategy schedule: TWAP/VWAP/POV).
- Post-trade: `src/exec/posttrade.py` (arrival vs exec, VWAP, implementation shortfall, broker attribution).
- Microstructure: `src/exec/microstructure.py` (spread/depth proxies, linear impact).
- OMS integration: `src/core/oms_simulator.py` now records pre/post-trade TCA in audits.

## How to Use
- Pre-trade estimate: `pretrade_estimate(notional, adv, TCAConfig())` → expected bps + schedule.
- Post-trade metrics: `posttrade_metrics(fills, arrival_px, vwap_px, side)` → slippage/shortfall + broker attribution.
- OMS sim: instantiate `ExecutionSimulator(tca_config=TCAConfig(), adv_lookup=1_000_000)`; audit JSONL includes pre/post TCA.
- Real ADV/spread/VWAP: use callables from `src/exec/providers/polygon_hooks.py` or `src/exec/providers/finnhub_hooks.py` and pass to `ExecutionSimulator` as `adv_lookup` / `spread_lookup`, or compute VWAP via those helpers.

## Assumptions & Defaults
- Flat spread input; impact linear with %ADV; equal-slice TWAP/VWAP; POV uses `pov_participation`.
- Venue weights are placeholders; VWAP uses provided price (no live tape).

## Next Steps
- Add live market data hooks for spread/depth and venue routing.
- Add VWAP benchmark calc from real intraday bars; add POV sizing vs live volume.
- Add broker/venue performance tracking over time; add dashboards and alerts.


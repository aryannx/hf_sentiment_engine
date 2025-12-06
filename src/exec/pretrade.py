from __future__ import annotations

from typing import List

from exec.config import TCAConfig
from exec.models import PreTradeEstimate


def estimate_slippage(notional: float, adv: float, spread_bps: float, impact_coeff: float) -> float:
    if adv <= 0:
        return spread_bps
    participation = notional / adv
    impact = impact_coeff * participation * 100  # bps per % ADV
    return spread_bps + impact


def build_schedule(strategy: str, slices: int, pov_participation: float) -> List[float]:
    if strategy.upper() == "POV":
        return [pov_participation] * slices
    # TWAP/VWAP simplified equal slices
    return [1 / slices] * slices


def pretrade_estimate(notional: float, adv: float, cfg: TCAConfig, ticker: str | None = None) -> PreTradeEstimate:
    spread_bps = cfg.spread_bps_by_ticker.get(ticker, cfg.default_spread_bps) if ticker else cfg.default_spread_bps
    slippage_bps = estimate_slippage(
        notional,
        adv,
        spread_bps,
        cfg.impact.impact_coefficient,
    )
    schedule = build_schedule(cfg.strategy.name, cfg.strategy.slices, cfg.strategy.pov_participation)
    return PreTradeEstimate(
        expected_slippage_bps=slippage_bps,
        expected_impact_bps=slippage_bps - spread_bps,
        strategy=cfg.strategy.name,
        schedule=schedule,
    )


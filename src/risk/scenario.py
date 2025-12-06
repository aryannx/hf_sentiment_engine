from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import numpy as np

from risk.models import Position

# Simple crisis shock templates (pct moves)
CRISIS_SHOCKS: Dict[str, Dict[str, float]] = {
    "gfc_2008": {"SPY": -0.35, "QQQ": -0.4, "LQD": -0.1, "HYG": -0.2},
    "covid_2020": {"SPY": -0.3, "QQQ": -0.28, "LQD": -0.08, "HYG": -0.18},
}


def shock_positions(positions: List[Position], shocks: Dict[str, float]) -> float:
    """
    Apply percentage shocks per ticker; return PnL impact.
    """
    pnl = 0.0
    for p in positions:
        shock = shocks.get(p.ticker, 0.0)
        pnl += p.notional * shock
    return pnl


def parametric_var(returns: Iterable[float], alpha: float = 0.99) -> float:
    arr = np.asarray(list(returns))
    if arr.size == 0:
        return 0.0
    mean = arr.mean()
    std = arr.std()
    z = 2.33 if alpha == 0.99 else 1.65
    return -(mean - z * std)


def historical_var(returns: Iterable[float], alpha: float = 0.99) -> float:
    arr = np.asarray(list(returns))
    if arr.size == 0:
        return 0.0
    return -np.percentile(arr, (1 - alpha) * 100)


def run_scenarios(positions: List[Position], scenarios: Dict[str, Dict[str, float]]) -> List[Tuple[str, float]]:
    """
    scenarios: name -> {ticker: pct_shock}
    """
    results = []
    for name, shocks in scenarios.items():
        pnl = shock_positions(positions, shocks)
        results.append((name, pnl))
    return results


def apply_crisis_scenarios(positions: List[Position]) -> List[Tuple[str, float]]:
    return run_scenarios(positions, CRISIS_SHOCKS)


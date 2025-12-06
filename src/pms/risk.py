from __future__ import annotations

from typing import Dict


def gross_net_exposure(positions: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
    gross = 0.0
    net = 0.0
    for tkr, qty in positions.items():
        val = qty * prices.get(tkr, 0.0)
        gross += abs(val)
        net += val
    return {"gross": gross, "net": net}


def simple_leverage(gross: float, equity: float) -> float:
    return gross / equity if equity else 0.0


def stress_bump(positions: Dict[str, float], prices: Dict[str, float], shock_pct: float = -0.1) -> float:
    pnl = 0.0
    for tkr, qty in positions.items():
        px = prices.get(tkr, 0.0)
        pnl += qty * (px * shock_pct)
    return pnl


def margin_placeholder(gross: float, margin_rate: float = 0.5) -> float:
    return gross * margin_rate


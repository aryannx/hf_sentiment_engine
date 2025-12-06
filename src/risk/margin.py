from __future__ import annotations

from typing import Dict, List

from risk.models import Position


def margin_requirement(positions: List[Position], haircuts: Dict[str, float], default_haircut: float = 0.15) -> float:
    req = 0.0
    for p in positions:
        hc = haircuts.get(p.ticker, default_haircut)
        req += abs(p.notional) * hc
    return req


def leverage_ratio(positions: List[Position], nav: float) -> float:
    gross = sum(abs(p.notional) for p in positions)
    return gross / nav if nav else 0.0


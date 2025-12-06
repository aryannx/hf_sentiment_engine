from __future__ import annotations

from typing import List, Dict

from risk.models import Position


def aggregate_greeks(positions: List[Position]) -> Dict[str, float]:
    """
    Placeholder Greek aggregator for future options support.
    """
    delta = sum(p.delta for p in positions)
    gamma = sum(p.gamma for p in positions)
    vega = sum(p.vega for p in positions)
    return {"delta": delta, "gamma": gamma, "vega": vega}


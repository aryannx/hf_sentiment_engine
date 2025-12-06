from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from exec.models import PostTradeMetrics


def arrival_slippage(exec_px: float, arrival_px: float, side: str) -> float:
    diff = exec_px - arrival_px
    bps = diff / arrival_px * 10_000
    return bps if side.lower() == "buy" else -bps


def vwap_slippage(exec_px: float, vwap_px: float, side: str) -> float:
    diff = exec_px - vwap_px
    bps = diff / vwap_px * 10_000
    return bps if side.lower() == "buy" else -bps


def implementation_shortfall(avg_exec_px: float, arrival_px: float, side: str) -> float:
    return arrival_slippage(avg_exec_px, arrival_px, side)


def broker_attribution(fills: List[Dict]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    notional: Dict[str, float] = {}
    for f in fills:
        broker = f.get("venue", "UNKNOWN")
        px = f["px"]
        qty = f["qty"]
        side = f.get("side", "buy")
        slip = arrival_slippage(px, f.get("arrival_px", px), side)
        totals[broker] = totals.get(broker, 0.0) + slip * qty
        notional[broker] = notional.get(broker, 0.0) + qty
    return {b: totals[b] / notional[b] for b in totals if notional[b] != 0}


def posttrade_metrics(
    fills: List[Dict],
    arrival_px: float,
    vwap_px: Optional[float],
    side: str,
) -> PostTradeMetrics:
    if not fills:
        return PostTradeMetrics(0.0, 0.0, 0.0, {})
    qtys = np.array([f["qty"] for f in fills])
    pxs = np.array([f["px"] for f in fills])
    avg_exec = float(np.average(pxs, weights=qtys))
    arrival_bps = arrival_slippage(avg_exec, arrival_px, side)
    vwap_bps = vwap_slippage(avg_exec, vwap_px if vwap_px else arrival_px, side)
    impl_shortfall = implementation_shortfall(avg_exec, arrival_px, side)
    brokers = broker_attribution(fills)
    return PostTradeMetrics(arrival_bps, vwap_bps, impl_shortfall, brokers)


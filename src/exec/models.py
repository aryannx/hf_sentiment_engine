from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PreTradeEstimate:
    expected_slippage_bps: float
    expected_impact_bps: float
    strategy: str
    schedule: List[float]


@dataclass
class PostTradeMetrics:
    arrival_slippage_bps: float
    vwap_slippage_bps: float
    implementation_shortfall_bps: float
    broker_attribution: Optional[dict] = None


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ExecutionStrategyConfig:
    name: str = "TWAP"  # TWAP/VWAP/POV
    slices: int = 4
    pov_participation: float = 0.1  # 10% of volume


@dataclass
class ImpactModel:
    base_bps: float = 5.0
    adv_floor: float = 1_000_000.0
    impact_coefficient: float = 0.5  # bps per % ADV


@dataclass
class VenueWeights:
    venues: Dict[str, float] = field(default_factory=lambda: {"LIT": 0.7, "DARK": 0.3})


@dataclass
class TCAConfig:
    default_spread_bps: float = 5.0
    spread_bps_by_ticker: Dict[str, float] = field(default_factory=dict)
    impact: ImpactModel = field(default_factory=ImpactModel)
    strategy: ExecutionStrategyConfig = field(default_factory=ExecutionStrategyConfig)
    venues: VenueWeights = field(default_factory=VenueWeights)
    venue_latency_ms: Dict[str, float] = field(default_factory=lambda: {"LIT": 5.0, "DARK": 15.0, "ALPACA": 10.0, "IBKR": 7.0})


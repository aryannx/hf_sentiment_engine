from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Limit:
    name: str
    threshold: float
    severity: str = "block"  # "block" or "warn"
    description: Optional[str] = None


@dataclass
class LayerLimits:
    max_position_pct: float = 0.05  # 5% of NAV per single position
    max_gross_leverage: float = 2.0
    max_net_leverage: float = 1.0
    sector_caps: Dict[str, float] = field(default_factory=dict)  # sector -> pct of NAV
    concentration_limit: float = 0.2  # top position share of NAV
    liquidity_buffer_pct: float = 0.05  # required cash buffer


@dataclass
class RiskConfig:
    strategy_limits: LayerLimits = field(default_factory=LayerLimits)
    portfolio_limits: LayerLimits = field(default_factory=LayerLimits)
    firm_limits: LayerLimits = field(default_factory=LayerLimits)
    margin_haircuts: Dict[str, float] = field(default_factory=dict)  # ticker/asset -> haircut
    stress_shocks: Dict[str, float] = field(default_factory=lambda: {"SPY": -0.1})
    var_alpha: float = 0.99
    correlation_threshold: float = 0.8  # warn when pairwise correlation exceeds


def default_risk_config() -> RiskConfig:
    return RiskConfig(
        strategy_limits=LayerLimits(
            max_position_pct=0.05,
            max_gross_leverage=2.0,
            max_net_leverage=1.0,
            sector_caps={"TECH": 0.3, "FIN": 0.25},
            concentration_limit=0.2,
            liquidity_buffer_pct=0.05,
        ),
        portfolio_limits=LayerLimits(
            max_position_pct=0.07,
            max_gross_leverage=2.5,
            max_net_leverage=1.5,
            sector_caps={"TECH": 0.35, "FIN": 0.3},
            concentration_limit=0.25,
            liquidity_buffer_pct=0.03,
        ),
        firm_limits=LayerLimits(
            max_position_pct=0.1,
            max_gross_leverage=3.0,
            max_net_leverage=2.0,
            sector_caps={},
            concentration_limit=0.3,
            liquidity_buffer_pct=0.02,
        ),
        margin_haircuts={},
        stress_shocks={"SPY": -0.1},
        var_alpha=0.99,
    )


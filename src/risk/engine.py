from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from risk.config import LayerLimits, RiskConfig
from risk.models import Exposure, Position
from risk.factors import factor_exposures, high_correlations


@dataclass
class Breach:
    level: str  # strategy / portfolio / firm
    name: str
    severity: str
    message: str


class RiskEngine:
    def __init__(self, config: RiskConfig):
        self.config = config

    def compute_exposure(self, positions: List[Position], nav: float) -> Exposure:
        long = sum(p.notional for p in positions if p.notional > 0)
        short = sum(abs(p.notional) for p in positions if p.notional < 0)
        gross = long + short
        net = long - short
        beta_adj = sum(p.notional * p.beta for p in positions)
        return Exposure(gross=gross, net=net, long=long, short=short, beta_adjusted_net=beta_adj, nav=nav)

    def _check_layer(self, exposure: Exposure, positions: List[Position], limits: LayerLimits, level: str) -> List[Breach]:
        breaches: List[Breach] = []

        def add(name: str, severity: str, msg: str):
            breaches.append(Breach(level=level, name=name, severity=severity, message=msg))

        # Gross/net leverage
        if exposure.gross_leverage > limits.max_gross_leverage:
            add("max_gross_leverage", "block", f"Gross leverage {exposure.gross_leverage:.2f} > {limits.max_gross_leverage:.2f}")
        if exposure.net_leverage > limits.max_net_leverage:
            add("max_net_leverage", "warn", f"Net leverage {exposure.net_leverage:.2f} > {limits.max_net_leverage:.2f}")

        # Position concentration
        for p in positions:
            pct_nav = abs(p.notional) / exposure.nav if exposure.nav else 0.0
            if pct_nav > limits.max_position_pct:
                add("max_position_pct", "block", f"{p.ticker} at {pct_nav:.2%} > {limits.max_position_pct:.2%}")
        if positions:
            top = max(abs(p.notional) for p in positions) / exposure.nav if exposure.nav else 0.0
            if top > limits.concentration_limit:
                add("concentration_limit", "warn", f"Top position {top:.2%} > {limits.concentration_limit:.2%}")

        # Sector caps
        if limits.sector_caps:
            sector_notional: Dict[str, float] = {}
            for p in positions:
                if not p.sector:
                    continue
                sector_notional[p.sector] = sector_notional.get(p.sector, 0.0) + abs(p.notional)
            for sector, limit_pct in limits.sector_caps.items():
                pct = (sector_notional.get(sector, 0.0) / exposure.nav) if exposure.nav else 0.0
                if pct > limit_pct:
                    add("sector_cap", "warn", f"Sector {sector} at {pct:.2%} > {limit_pct:.2%}")

        # Liquidity buffer (simple cash proxy)
        if limits.liquidity_buffer_pct > 0:
            buffer_needed = limits.liquidity_buffer_pct * exposure.nav
            if exposure.nav - exposure.gross < buffer_needed:
                add(
                    "liquidity_buffer",
                    "warn",
                    f"Liquidity buffer short: need {buffer_needed:.0f}, have {exposure.nav - exposure.gross:.0f}",
                )

        return breaches

    def _aggregate_greeks(self, positions: List[Position]) -> Dict[str, float]:
        delta = sum(p.delta for p in positions)
        gamma = sum(p.gamma for p in positions)
        vega = sum(p.vega for p in positions)
        return {"delta": delta, "gamma": gamma, "vega": vega}

    def check_limits(
        self,
        positions: List[Position],
        nav: float,
        strategy: str = "default",
        portfolio: str = "default",
        factor_betas: Optional[Dict[str, Dict[str, float]]] = None,
        returns: Optional[pd.DataFrame] = None,
    ) -> Dict:
        exposure = self.compute_exposure(positions, nav)
        breaches: List[Breach] = []
        breaches += self._check_layer(exposure, positions, self.config.strategy_limits, "strategy")
        breaches += self._check_layer(exposure, positions, self.config.portfolio_limits, "portfolio")
        breaches += self._check_layer(exposure, positions, self.config.firm_limits, "firm")

        factor_exp = {}
        if factor_betas:
            factor_exp = factor_exposures(positions, factor_betas, nav)
            for factor, exp in factor_exp.items():
                if abs(exp) > 1.0:
                    breaches.append(
                        Breach(
                            level="factor",
                            name=f"factor_{factor}",
                            severity="warn",
                            message=f"{factor} exposure {exp:.2f}x NAV",
                        )
                    )

        corr_flags: List = []
        if returns is not None:
            pairs = high_correlations(returns, threshold=self.config.correlation_threshold)
            for a, b, val in pairs:
                corr_flags.append((a, b, val))
                breaches.append(
                    Breach(
                        level="correlation",
                        name="pairwise_corr",
                        severity="warn",
                        message=f"{a}-{b} correlation {val:.2f} exceeds {self.config.correlation_threshold:.2f}",
                    )
                )

        decision = "pass"
        if any(b.severity == "block" for b in breaches):
            decision = "block"
        elif any(b.severity == "warn" for b in breaches):
            decision = "warn"

        greeks = self._aggregate_greeks(positions)

        return {
            "decision": decision,
            "exposure": exposure,
            "breaches": breaches,
            "context": {"strategy": strategy, "portfolio": portfolio},
            "factor_exposures": factor_exp,
            "correlation_flags": corr_flags,
            "greeks": greeks,
        }


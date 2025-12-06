from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from src.pms.models import Portfolio, Account


@dataclass
class PMSConfig:
    portfolios: List[Portfolio] = field(default_factory=list)


def demo_pms_config() -> PMSConfig:
    """
    Minimal demo configuration with a single portfolio and account.
    """
    acct = Account(name="DemoAcct", cash=100000.0, positions={})
    port = Portfolio(
        name="DemoPortfolio",
        accounts=[acct],
        target_weights={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4},
        benchmark="SPY",
        turnover_cap=0.5,
        drift_threshold=0.02,
        cash_buffer_pct=0.02,
    )
    return PMSConfig(portfolios=[port])


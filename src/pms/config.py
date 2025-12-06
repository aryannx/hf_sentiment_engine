from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from src.pms.models import Portfolio, Account


@dataclass
class PMSConfig:
    portfolios: List[Portfolio] = field(default_factory=list)
    master_feeders: Dict[str, List[str]] = field(default_factory=dict)  # master -> [feeder portfolios]
    account_routing: Dict[str, Dict[str, float]] = field(default_factory=dict)  # portfolio -> account weights


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
    return PMSConfig(
        portfolios=[port],
        master_feeders={"DemoMaster": ["DemoPortfolio"]},
        account_routing={"DemoPortfolio": {"DemoAcct": 1.0}},
    )


def demo_master_feeder_config() -> PMSConfig:
    master_acct = Account(name="MasterAcct", cash=200_000.0, positions={})
    feeder_us = Account(name="FeederUS", cash=100_000.0, positions={})
    feeder_off = Account(name="FeederOffshore", cash=150_000.0, positions={})

    master_port = Portfolio(
        name="MasterFund",
        accounts=[master_acct],
        target_weights={"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3},
        benchmark="SPY",
        turnover_cap=0.4,
        drift_threshold=0.015,
        cash_buffer_pct=0.03,
        target_vol=0.12,
        account_weights={"MasterAcct": 1.0},
    )

    feeder_port = Portfolio(
        name="FeederComplex",
        accounts=[feeder_us, feeder_off],
        target_weights={"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3},
        benchmark="SPY",
        turnover_cap=0.4,
        drift_threshold=0.015,
        cash_buffer_pct=0.03,
        target_vol=0.12,
        account_weights={"FeederUS": 0.4, "FeederOffshore": 0.6},
    )

    return PMSConfig(
        portfolios=[master_port, feeder_port],
        master_feeders={"MasterFund": ["FeederComplex"]},
        account_routing={
            "MasterFund": {"MasterAcct": 1.0},
            "FeederComplex": {"FeederUS": 0.4, "FeederOffshore": 0.6},
        },
    )


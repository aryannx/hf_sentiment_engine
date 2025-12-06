from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Account:
    name: str
    cash: float = 0.0
    positions: Dict[str, float] = field(default_factory=dict)
    benchmark: Optional[str] = None


@dataclass
class Portfolio:
    name: str
    accounts: List[Account]
    target_weights: Dict[str, float] = field(default_factory=dict)  # ticker -> weight
    benchmark: Optional[str] = None
    account_weights: Optional[Dict[str, float]] = None  # allocate orders across accounts
    turnover_cap: float = 1.0  # max 100% turnover by default
    drift_threshold: float = 0.01  # 1% drift triggers rebalance
    cash_buffer_pct: float = 0.02  # keep 2% cash
    constraints: Dict[str, float] = field(default_factory=dict)  # e.g., sector caps
    target_vol: Optional[float] = None  # annualized vol target (e.g., 0.1)


@dataclass
class RebalanceOrder:
    ticker: str
    side: str  # BUY/SELL
    qty: float
    px: float
    portfolio: str
    account: str


@dataclass
class RebalanceProposal:
    portfolio: str
    orders: List[RebalanceOrder]
    turnover: float
    notes: Optional[str] = None


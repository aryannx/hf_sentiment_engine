from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Position:
    ticker: str
    qty: float
    price: float
    sector: Optional[str] = None
    beta: float = 1.0
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0

    @property
    def notional(self) -> float:
        return self.qty * self.price


@dataclass
class Exposure:
    gross: float
    net: float
    long: float
    short: float
    beta_adjusted_net: float
    nav: float

    @property
    def gross_leverage(self) -> float:
        return self.gross / self.nav if self.nav else 0.0

    @property
    def net_leverage(self) -> float:
        return abs(self.net) / self.nav if self.nav else 0.0


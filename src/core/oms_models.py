from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"
    GTC = "GTC"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    order_id: str
    ticker: str
    side: OrderSide
    qty: float
    px: float  # arrival/limit reference
    tif: TimeInForce = TimeInForce.DAY
    metadata: Dict = field(default_factory=dict)
    status: OrderStatus = OrderStatus.NEW


@dataclass
class Fill:
    order_id: str
    fill_id: str
    ticker: str
    side: OrderSide
    qty: float
    px: float
    ts: datetime
    venue: str = "SIM"
    slippage_bps: Optional[float] = None


@dataclass
class Allocation:
    order_id: str
    account: str
    qty: float


@dataclass
class Route:
    order_id: str
    venue: str
    qty: float
    px: float
    tif: TimeInForce
    status: OrderStatus = OrderStatus.NEW
    fills: List[Fill] = field(default_factory=list)


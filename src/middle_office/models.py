from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class BreakSeverity(str, Enum):
    WARN = "warn"
    BLOCK = "block"


class BreakStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass
class BookedTrade:
    trade_id: str
    ticker: str
    side: str  # BUY/SELL
    qty: float
    px: float
    trade_date: datetime
    settle_date: datetime
    status: SettlementStatus = SettlementStatus.PENDING
    source: str = "OMS"
    metadata: Dict = field(default_factory=dict)


@dataclass
class SettlementInstruction:
    trade_id: str
    settle_date: datetime
    amount: float
    currency: str = "USD"
    status: SettlementStatus = SettlementStatus.PENDING


@dataclass
class PositionSnapshot:
    as_of: datetime
    positions: Dict[str, float]  # ticker -> qty
    cash: float
    source: str = "IBOR"


@dataclass
class BreakRecord:
    as_of: datetime
    ticker: str
    category: str  # qty/cash/price
    fund_value: float
    broker_value: float
    custodian_value: float
    materiality: float
    severity: BreakSeverity = BreakSeverity.WARN
    status: BreakStatus = BreakStatus.OPEN
    notes: Optional[str] = None
    resolution: Optional[str] = None


@dataclass
class CorporateAction:
    as_of: datetime
    ticker: str
    action_type: str  # DIVIDEND, SPLIT
    amount: Optional[float] = None  # per-share dividend
    ratio: Optional[float] = None   # split ratio (e.g., 2.0 = 2-for-1)


@dataclass
class CashMovement:
    as_of: datetime
    amount: float
    currency: str = "USD"
    source: str = "fund"


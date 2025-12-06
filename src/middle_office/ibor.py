from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

from src.middle_office.models import PositionSnapshot, CorporateAction, CashMovement


@dataclass
class IBOR:
    cash: float = 0.0
    positions: Dict[str, float] = field(default_factory=dict)

    def apply_trade(self, ticker: str, qty: float, px: float, side: str) -> None:
        sign = 1 if side.upper() == "BUY" else -1
        self.cash -= sign * qty * px
        self.positions[ticker] = self.positions.get(ticker, 0.0) + sign * qty

    def snapshot(self) -> PositionSnapshot:
        return PositionSnapshot(
            as_of=datetime.utcnow(),
            positions=dict(self.positions),
            cash=self.cash,
        )

    def apply_corporate_action(self, action: CorporateAction) -> None:
        """Adjust positions/cash for splits and dividends."""
        qty = self.positions.get(action.ticker, 0.0)
        if qty == 0:
            return
        if action.action_type.upper() == "DIVIDEND" and action.amount is not None:
            self.cash += qty * action.amount
        elif action.action_type.upper() == "SPLIT" and action.ratio is not None:
            self.positions[action.ticker] = qty * action.ratio

    def apply_cash_movement(self, movement: CashMovement) -> None:
        self.cash += movement.amount


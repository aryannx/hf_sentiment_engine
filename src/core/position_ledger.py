from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from src.core.oms_models import Fill, OrderSide


@dataclass
class Position:
    qty: float = 0.0
    avg_px: float = 0.0


class PositionLedger:
    """
    Tracks positions, cash, and PnL from fills.
    """

    def __init__(self, starting_cash: float = 100000.0):
        self.cash = starting_cash
        self.positions: Dict[str, Position] = {}
        self.realized_pnl = 0.0

    def apply_fill(self, fill: Fill) -> None:
        pos = self.positions.get(fill.ticker, Position())
        if fill.side == OrderSide.BUY:
            new_qty = pos.qty + fill.qty
            new_cost = pos.avg_px * pos.qty + fill.px * fill.qty
            pos.qty = new_qty
            pos.avg_px = new_cost / new_qty if new_qty != 0 else 0.0
            self.cash -= fill.px * fill.qty
        else:  # SELL
            qty_to_close = min(pos.qty, fill.qty)
            self.realized_pnl += qty_to_close * (fill.px - pos.avg_px)
            pos.qty -= qty_to_close
            self.cash += fill.px * fill.qty
            # If over-sell, assume shorting at fill price
            if fill.qty > qty_to_close:
                short_qty = fill.qty - qty_to_close
                pos.qty -= short_qty
                pos.avg_px = fill.px

        self.positions[fill.ticker] = pos

    def apply_fills(self, fills) -> None:
        for f in fills:
            self.apply_fill(f)

    def equity(self, marks: Dict[str, float]) -> float:
        unrealized = 0.0
        for tkr, pos in self.positions.items():
            px = marks.get(tkr, pos.avg_px)
            unrealized += pos.qty * (px - pos.avg_px)
        return self.cash + self.realized_pnl + unrealized

    def snapshot(self, marks: Dict[str, float]) -> Dict[str, float]:
        return {
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "equity": self.equity(marks),
            "positions": {t: {"qty": p.qty, "avg_px": p.avg_px} for t, p in self.positions.items()},
        }


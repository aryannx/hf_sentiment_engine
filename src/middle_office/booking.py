from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from src.middle_office.models import BookedTrade, SettlementInstruction, SettlementStatus
from src.middle_office.storage import append_jsonl


class BookingEngine:
    """
    Ingest fills and create booked trades + settlement instructions.
    """

    def __init__(self, audit_dir="logs/middle_office"):
        from pathlib import Path

        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def book_fills(self, fills: List[dict]) -> List[BookedTrade]:
        booked = []
        for f in fills:
            trade_date = f.get("ts", datetime.utcnow())
            if isinstance(trade_date, str):
                trade_date = datetime.fromisoformat(trade_date)
            settle_date = trade_date + timedelta(days=2)
            side = f.get("side", "BUY")
            qty = f.get("qty", 0.0)
            px = f.get("px", 0.0)
            trade = BookedTrade(
                trade_id=f.get("fill_id", f.get("order_id", "")),
                ticker=f.get("ticker", ""),
                side=side,
                qty=qty,
                px=px,
                trade_date=trade_date,
                settle_date=settle_date,
                status=SettlementStatus.PENDING,
                source=f.get("venue", "SIM"),
                metadata={"order_id": f.get("order_id")},
            )
            booked.append(trade)
            self._audit(trade)
        return booked

    def settlement_instructions(self, trades: List[BookedTrade]) -> List[SettlementInstruction]:
        inst = []
        for t in trades:
            amount = t.qty * t.px * (1 if t.side == "SELL" else -1)
            inst.append(
                SettlementInstruction(
                    trade_id=t.trade_id,
                    settle_date=t.settle_date,
                    amount=amount,
                    currency="USD",
                    status=SettlementStatus.PENDING,
                )
            )
        return inst

    def _audit(self, trade: BookedTrade) -> None:
        append_jsonl(self.audit_dir / "bookings.jsonl", trade.__dict__)


from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from src.core.oms_models import Fill, Order, OrderSide, OrderStatus
from src.core.oms_config import ExecutionConfig


class ExecutionSimulator:
    """
    Simple execution simulator with slippage and partial fills.
    """

    def __init__(self, config: ExecutionConfig = ExecutionConfig(), audit_dir: Path = Path("logs/oms")):
        self.config = config
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        if config.seed is not None:
            random.seed(config.seed)

    def execute(self, order: Order) -> Tuple[Order, List[Fill]]:
        cfg = self.config
        remaining = order.qty
        fills: List[Fill] = []
        partials = 0

        while remaining > 0:
            # Determine fill qty
            if partials < cfg.max_partials and random.random() < cfg.partial_fill_prob:
                fill_qty = remaining * 0.5
                partials += 1
            else:
                fill_qty = remaining

            exec_px = self._apply_slippage(order.px, order.side, cfg.slippage_bps)
            fill = Fill(
                order_id=order.order_id,
                fill_id=f"{order.order_id}-{len(fills)+1}",
                ticker=order.ticker,
                side=order.side,
                qty=fill_qty,
                px=exec_px,
                ts=datetime.utcnow(),
                venue=cfg.venue,
                slippage_bps=cfg.slippage_bps,
            )
            fills.append(fill)
            remaining -= fill_qty

            if partials >= cfg.max_partials:
                break

        filled_qty = sum(f.qty for f in fills)
        if filled_qty == order.qty:
            order.status = OrderStatus.FILLED
        elif filled_qty == 0:
            order.status = OrderStatus.REJECTED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        self._write_audit(order, fills)
        return order, fills

    @staticmethod
    def _apply_slippage(px: float, side: OrderSide, slippage_bps: float) -> float:
        bump = px * slippage_bps / 10_000
        return px + bump if side == OrderSide.BUY else px - bump

    def _write_audit(self, order: Order, fills: List[Fill]) -> None:
        try:
            payload = {
                "ts": datetime.utcnow().isoformat(),
                "order": order.__dict__,
                "fills": [f.__dict__ for f in fills],
                "config": self.config.__dict__,
            }
            path = self.audit_dir / f"oms_{datetime.utcnow().date()}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, default=str) + "\n")
        except Exception:
            pass


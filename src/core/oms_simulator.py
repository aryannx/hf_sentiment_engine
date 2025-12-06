from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from src.core.oms_models import Fill, Order, OrderSide, OrderStatus
from src.core.oms_config import ExecutionConfig
from exec.config import TCAConfig
from exec.pretrade import pretrade_estimate
from exec.posttrade import posttrade_metrics
from exec.data_sources import compute_vwap_from_bars


class ExecutionSimulator:
    """
    Simple execution simulator with slippage and partial fills.
    """

    def __init__(
        self,
        config: ExecutionConfig = ExecutionConfig(),
        audit_dir: Path = Path("logs/oms"),
        tca_config: TCAConfig = TCAConfig(),
        adv_lookup: float | dict | callable = 1_000_000.0,
        spread_lookup: float | dict | callable | None = None,
        vwap_bars: Path | None = None,
    ):
        self.config = config
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        if config.seed is not None:
            random.seed(config.seed)
        self.tca_config = tca_config
        self.adv_lookup = adv_lookup
        self.spread_lookup = spread_lookup
        self.vwap_bars = vwap_bars

    def execute(self, order: Order) -> Tuple[Order, List[Fill]]:
        cfg = self.config
        remaining = order.qty
        fills: List[Fill] = []
        partials = 0

        adv = self._resolve_lookup(self.adv_lookup, order.ticker, default=1_000_000.0)
        spread = self._resolve_lookup(self.spread_lookup, order.ticker, default=None)
        if isinstance(spread, (int, float)):
            self.tca_config.spread_bps_by_ticker[order.ticker] = float(spread)
        estimate = pretrade_estimate(order.qty * order.px, adv, self.tca_config, ticker=order.ticker)

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

        vwap_px = order.px
        if self.vwap_bars and Path(self.vwap_bars).exists():
            try:
                import pandas as pd

                bars = pd.read_csv(self.vwap_bars)
                vwap_px = compute_vwap_from_bars(bars) or order.px
            except Exception:
                vwap_px = order.px

        tca = posttrade_metrics(
            [f.__dict__ for f in fills],
            arrival_px=order.px,
            vwap_px=vwap_px,
            side=order.side.name.lower(),
        )

        self._write_audit(order, fills, estimate, tca)
        return order, fills

    @staticmethod
    def _apply_slippage(px: float, side: OrderSide, slippage_bps: float) -> float:
        bump = px * slippage_bps / 10_000
        return px + bump if side == OrderSide.BUY else px - bump

    def _write_audit(self, order: Order, fills: List[Fill], estimate=None, tca=None) -> None:
        try:
            payload = {
                "ts": datetime.utcnow().isoformat(),
                "order": order.__dict__,
                "fills": [f.__dict__ for f in fills],
                "config": self.config.__dict__,
                "pretrade": estimate.__dict__ if estimate else None,
                "posttrade": tca.__dict__ if tca else None,
            }
            path = self.audit_dir / f"oms_{datetime.utcnow().date()}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, default=str) + "\n")
        except Exception:
            pass

    @staticmethod
    def _resolve_lookup(source, ticker: str, default=None):
        if source is None:
            return default
        if callable(source):
            try:
                return source(ticker)
            except Exception:
                return default
        if isinstance(source, dict):
            return source.get(ticker, default)
        return source


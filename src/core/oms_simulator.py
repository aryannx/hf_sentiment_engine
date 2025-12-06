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
from exec.providers.polygon_hooks import vwap_from_polygon_minutes
from exec.providers.finnhub_hooks import vwap_from_finnhub


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
        vwap_provider: str | callable | None = None,
        broker_perf_log: Path = Path("logs/oms/broker_perf.jsonl"),
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
        self.vwap_provider = vwap_provider
        self.broker_perf_log = broker_perf_log
        self.broker_perf_log.parent.mkdir(parents=True, exist_ok=True)

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

        venues = list(self.tca_config.venues.venues.keys()) if getattr(self.tca_config, "venues", None) else [cfg.venue]
        weights = list(self.tca_config.venues.venues.values()) if getattr(self.tca_config, "venues", None) else [1.0]
        while remaining > 0:
            # Determine fill qty
            if partials < cfg.max_partials and random.random() < cfg.partial_fill_prob:
                fill_qty = remaining * 0.5
                partials += 1
            else:
                fill_qty = remaining

            exec_px = self._apply_slippage(order.px, order.side, cfg.slippage_bps)
            venue = cfg.venue
            if cfg.route_venues and venues and weights:
                venue = random.choices(venues, weights=weights, k=1)[0]
            fill = Fill(
                order_id=order.order_id,
                fill_id=f"{order.order_id}-{len(fills)+1}",
                ticker=order.ticker,
                side=order.side,
                qty=fill_qty,
                px=exec_px,
                ts=datetime.utcnow(),
                venue=venue,
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
        # VWAP from file if provided
        if self.vwap_bars and Path(self.vwap_bars).exists():
            try:
                import pandas as pd

                bars = pd.read_csv(self.vwap_bars)
                vwap_px = compute_vwap_from_bars(bars) or order.px
            except Exception:
                vwap_px = order.px
        # VWAP from provider callable/keyword
        elif self.vwap_provider:
            provider = self.vwap_provider
            if isinstance(provider, str):
                if provider == "polygon":
                    vwap_px = vwap_from_polygon_minutes(order.ticker) or order.px
                elif provider == "finnhub":
                    vwap_px = vwap_from_finnhub(order.ticker) or order.px
                else:
                    vwap_px = order.px
            else:
                vwap_px = self._resolve_lookup(provider, order.ticker, default=order.px)

        tca = posttrade_metrics(
            [f.__dict__ for f in fills],
            arrival_px=order.px,
            vwap_px=vwap_px,
            side=order.side.name.lower(),
        )

        self._write_audit(order, fills, estimate, tca)
        self._write_broker_perf(order, tca)
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

    def _write_broker_perf(self, order: Order, tca) -> None:
        if not tca or not getattr(tca, "broker_attribution", None):
            return
        try:
            payload = {
                "ts": datetime.utcnow().isoformat(),
                "order_id": order.order_id,
                "ticker": order.ticker,
                "brokers": tca.broker_attribution,
            }
            with self.broker_perf_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
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


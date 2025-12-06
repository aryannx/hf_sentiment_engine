from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from src.pms.models import Portfolio, RebalanceOrder, RebalanceProposal


@dataclass
class Rebalancer:
    """
    Computes drift vs targets and produces rebalance orders.
    """

    def compute_rebalance(
        self,
        portfolio: Portfolio,
        prices: Dict[str, float],
        *,
        realized_vol: float | None = None,
    ) -> RebalanceProposal:
        """
        Multi-account aware rebalancing with optional target-vol scaling.
        """
        target_weights = portfolio.target_weights
        account_weights = portfolio.account_weights or {
            acct.name: 1.0 / len(portfolio.accounts) for acct in portfolio.accounts
        }

        # Aggregate equity across accounts
        acct_equity = {}
        for acct in portfolio.accounts:
            eq = acct.cash + sum((prices.get(t, 0.0) * qty) for t, qty in acct.positions.items())
            acct_equity[acct.name] = eq
        total_equity = sum(acct_equity.values())

        # enforce cash buffer and optional target-vol scaling
        investable = total_equity * (1 - portfolio.cash_buffer_pct)
        scale = 1.0
        if portfolio.target_vol and realized_vol and realized_vol > 0:
            scale = min(portfolio.target_vol / realized_vol, 2.0)
            investable *= scale

        orders: List[RebalanceOrder] = []
        turnover_notional = 0.0

        for ticker, target_w in target_weights.items():
            desired_value = investable * target_w
            # current across accounts
            current_value = sum(prices.get(ticker, 0.0) * acct.positions.get(ticker, 0.0) for acct in portfolio.accounts)
            drift = (desired_value - current_value) / total_equity if total_equity else 0.0
            if abs(drift) < portfolio.drift_threshold:
                continue
            px = prices.get(ticker)
            if px is None or px <= 0:
                continue
            qty_diff_total = (desired_value - current_value) / px
            side = "BUY" if qty_diff_total > 0 else "SELL"
            # allocate to accounts
            for acct in portfolio.accounts:
                w = account_weights.get(acct.name, 0.0)
                acct_qty = qty_diff_total * w
                if abs(acct_qty) <= 0:
                    continue
                orders.append(
                    RebalanceOrder(
                        ticker=ticker,
                        side=side,
                        qty=abs(acct_qty),
                        px=px,
                        portfolio=portfolio.name,
                        account=acct.name,
                    )
                )
                turnover_notional += abs(acct_qty * px)

        turnover_ratio = turnover_notional / total_equity if total_equity else 0.0
        if turnover_ratio > portfolio.turnover_cap and turnover_ratio > 0:
            scale = portfolio.turnover_cap / turnover_ratio
            for o in orders:
                o.qty *= scale
            turnover_ratio = portfolio.turnover_cap

        return RebalanceProposal(
            portfolio=portfolio.name,
            orders=orders,
            turnover=turnover_ratio,
            notes=None,
        )

    def execute_orders(self, orders: List[RebalanceOrder], exec_sim) -> List[dict]:
        """
        Send rebalance orders through an OMS-like simulator, returning fills.
        """
        fills = []
        from src.core.oms_models import Order, OrderSide

        for idx, o in enumerate(orders):
            side_enum = OrderSide.BUY if o.side.upper() == "BUY" else OrderSide.SELL
            order = Order(
                order_id=f"REB-{idx}-{o.portfolio}-{o.account}",
                ticker=o.ticker,
                side=side_enum,
                qty=o.qty,
                px=o.px,
            )
            _, fs = exec_sim.execute(order)
            fills.extend(f.__dict__ for f in fs)
        return fills


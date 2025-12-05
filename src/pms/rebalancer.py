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
    ) -> RebalanceProposal:
        acct = portfolio.accounts[0]
        target_weights = portfolio.target_weights
        total_equity = acct.cash + sum((prices.get(t, 0.0) * qty) for t, qty in acct.positions.items())

        # enforce cash buffer
        investable = total_equity * (1 - portfolio.cash_buffer_pct)

        current_values = {t: prices.get(t, 0.0) * acct.positions.get(t, 0.0) for t in target_weights}
        current_weights = {
            t: (current_values.get(t, 0.0) / total_equity) if total_equity > 0 else 0.0 for t in target_weights
        }

        orders: List[RebalanceOrder] = []
        turnover_notional = 0.0

        for ticker, target_w in target_weights.items():
            desired_value = investable * target_w
            current_value = current_values.get(ticker, 0.0)
            drift = (desired_value - current_value) / total_equity if total_equity else 0.0
            if abs(drift) < portfolio.drift_threshold:
                continue
            px = prices.get(ticker)
            if px is None or px <= 0:
                continue
            qty_diff = (desired_value - current_value) / px
            side = "BUY" if qty_diff > 0 else "SELL"
            orders.append(
                RebalanceOrder(
                    ticker=ticker,
                    side=side,
                    qty=abs(qty_diff),
                    px=px,
                    portfolio=portfolio.name,
                    account=acct.name,
                )
            )
            turnover_notional += abs(qty_diff * px)

        turnover_ratio = turnover_notional / total_equity if total_equity else 0.0
        if turnover_ratio > portfolio.turnover_cap:
            # scale orders to respect turnover cap
            scale = portfolio.turnover_cap / turnover_ratio if turnover_ratio > 0 else 0
            for o in orders:
                o.qty *= scale
                turnover_ratio = portfolio.turnover_cap

        return RebalanceProposal(
            portfolio=portfolio.name,
            orders=orders,
            turnover=turnover_ratio,
            notes=None,
        )


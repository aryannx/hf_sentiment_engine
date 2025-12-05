from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def security_contribution(returns: pd.Series, weights: pd.Series) -> float:
    """
    Simple contribution = sum(weight * return).
    """
    aligned = pd.concat([returns, weights], axis=1).fillna(0.0)
    return float((aligned.iloc[:, 0] * aligned.iloc[:, 1]).sum())


def benchmark_excess(portfolio_ret: float, bench_ret: float) -> float:
    return portfolio_ret - bench_ret


def contribution_report(returns: Dict[str, float], weights: Dict[str, float]) -> Dict[str, float]:
    """
    Returns per-security contributions.
    """
    contrib = {}
    for tkr, r in returns.items():
        w = weights.get(tkr, 0.0)
        contrib[tkr] = w * r
    total = sum(contrib.values())
    contrib["total"] = total
    return contrib


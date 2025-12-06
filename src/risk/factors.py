from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from risk.models import Position


def factor_exposures(positions: List[Position], factor_betas: Dict[str, Dict[str, float]], nav: float) -> Dict[str, float]:
    """
    factor_betas: factor -> {ticker: beta}
    returns factor exposure as pct of NAV (beta-weighted notional)
    """
    exposures: Dict[str, float] = {}
    if nav == 0:
        return exposures
    for factor, mapping in factor_betas.items():
        beta_notional = 0.0
        for p in positions:
            beta = mapping.get(p.ticker, p.beta)
            beta_notional += p.notional * beta
        exposures[factor] = beta_notional / nav
    return exposures


def high_correlations(returns: pd.DataFrame, threshold: float = 0.8) -> List[Tuple[str, str, float]]:
    """
    Given returns DataFrame (columns=tickers), return pairs exceeding threshold.
    """
    pairs: List[Tuple[str, str, float]] = []
    if returns.empty or returns.shape[1] < 2:
        return pairs
    corr = returns.corr()
    cols = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            val = corr.iloc[i, j]
            if abs(val) >= threshold:
                pairs.append((cols[i], cols[j], val))
    return pairs


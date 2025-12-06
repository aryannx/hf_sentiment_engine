from __future__ import annotations

from typing import Dict


def gross_net_exposure(positions: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
    gross = 0.0
    net = 0.0
    for tkr, qty in positions.items():
        val = qty * prices.get(tkr, 0.0)
        gross += abs(val)
        net += val
    return {"gross": gross, "net": net}


def simple_leverage(gross: float, equity: float) -> float:
    return gross / equity if equity else 0.0


def stress_bump(positions: Dict[str, float], prices: Dict[str, float], shock_pct: float = -0.1) -> float:
    pnl = 0.0
    for tkr, qty in positions.items():
        px = prices.get(tkr, 0.0)
        pnl += qty * (px * shock_pct)
    return pnl


def margin_placeholder(gross: float, margin_rate: float = 0.5) -> float:
    return gross * margin_rate


def correlation_matrix(returns: Dict[str, list] | "pd.DataFrame"):
    import pandas as pd

    if isinstance(returns, dict):
        df = pd.DataFrame(returns)
    else:
        df = returns
    return df.corr()


def top_correlations(corr_df, top_n: int = 5):
    pairs = []
    cols = corr_df.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append((cols[i], cols[j], corr_df.iloc[i, j]))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs[:top_n]


def target_vol_scale(current_vol: float, target_vol: float) -> float:
    if current_vol <= 0 or target_vol <= 0:
        return 1.0
    return min(target_vol / current_vol, 2.0)


def margin_waterfall(gross: float, tiers: list[tuple[float, float]]) -> float:
    """
    tiers: list of (notional_threshold, margin_rate). Applies piecewise.
    """
    required = 0.0
    remaining = gross
    prev = 0.0
    for threshold, rate in tiers:
        slab = min(max(remaining - prev, 0.0), threshold - prev)
        required += slab * rate
        prev = threshold
    if remaining > prev:
        # apply last tier rate
        required += (remaining - prev) * tiers[-1][1]
    return required


def liquidity_buffer_check(cash: float, buffer_needed: float) -> bool:
    return cash >= buffer_needed


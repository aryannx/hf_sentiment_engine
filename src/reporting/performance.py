from __future__ import annotations

import pandas as pd
import numpy as np


def monthly_returns(equity_curve: pd.Series) -> pd.Series:
    if equity_curve.empty:
        return pd.Series(dtype=float)
    monthly = equity_curve.resample("M").last().pct_change().dropna()
    return monthly


def sharpe(returns: pd.Series, rf: float = 0.0) -> float:
    if returns.empty:
        return 0.0
    excess = returns - rf / 252
    return float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() != 0 else 0.0


def sortino(returns: pd.Series, rf: float = 0.0) -> float:
    if returns.empty:
        return 0.0
    excess = returns - rf / 252
    downside = excess[excess < 0]
    denom = downside.std()
    if denom == 0 or np.isnan(denom):
        return 0.0
    return float(np.sqrt(252) * excess.mean() / denom)


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    roll_max = equity_curve.cummax()
    dd = (equity_curve - roll_max) / roll_max
    return float(dd.min())


def performance_summary(equity_curve: pd.Series) -> dict:
    rets = equity_curve.pct_change().dropna()
    return {
        "total_return": float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0) if len(equity_curve) > 1 else 0.0,
        "sharpe": sharpe(rets),
        "sortino": sortino(rets),
        "max_drawdown": max_drawdown(equity_curve),
        "monthly_returns": monthly_returns(equity_curve).to_dict(),
    }


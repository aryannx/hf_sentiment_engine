import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.equities.equity_backtester import EquityBacktester


def _price_frame():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    close = [100, 102, 104, 103, 105]
    return pd.DataFrame({"Date": dates, "Close": close})


def test_run_backtest_computes_expected_equity_curve():
    df = _price_frame()
    signals = np.array([0.0, 1.0, 1.0, 1.0, 0.0])

    backtester = EquityBacktester(initial_cash=100_000, notional=1.0)
    metrics = backtester.run_backtest(
        "TEST",
        signals,
        df,
        print_trades=False,
    )

    raw_returns = df["Close"].pct_change().to_numpy()
    raw_returns = np.nan_to_num(raw_returns, nan=0.0)
    strat_returns = signals * raw_returns
    strat_returns[0] = 0.0
    expected_final = float((1.0 + strat_returns).cumprod()[-1] * backtester.initial_cash)

    assert metrics["final_value"] == pytest.approx(expected_final, rel=1e-9)
    assert len(metrics["trade_list"]) == 1
    assert metrics["trades"] >= 1


def test_run_backtest_with_risk_multiplier_and_oos_split():
    df = _price_frame()
    signals = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
    risk_mult = pd.Series([1.0, 0.5, 0.5, 0.0, 1.0], index=df.index)

    backtester = EquityBacktester(initial_cash=50_000, notional=1.0)
    metrics = backtester.run_backtest(
        "TEST",
        signals,
        df,
        risk_multiplier=risk_mult,
        print_trades=False,
        split_ratio=0.6,
        validate_oos=True,
    )

    raw_returns = df["Close"].pct_change().to_numpy()
    raw_returns = np.nan_to_num(raw_returns, nan=0.0)
    strat_returns = signals * raw_returns * risk_mult.to_numpy()
    strat_returns[0] = 0.0
    expected_final = float((1.0 + strat_returns).cumprod()[-1] * backtester.initial_cash)

    assert metrics["final_value"] == pytest.approx(expected_final, rel=1e-9)
    assert "training_metrics" in metrics
    assert "oos_metrics" in metrics
    assert metrics["training_metrics"]["start_date"] <= metrics["training_metrics"]["end_date"]


def test_transaction_costs_penalize_signal_changes():
    backtester = EquityBacktester()
    returns = np.array([0.0, 0.01, -0.02])
    signals = np.array([0.0, 1.0, 1.0])
    adjusted = backtester._apply_transaction_costs(returns, signals, cost_bps=10)
    expected = returns.copy()
    expected[1] -= 0.001

    assert adjusted.tolist() == expected.tolist()


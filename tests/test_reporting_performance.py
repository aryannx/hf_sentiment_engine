import pandas as pd
from src.reporting.performance import performance_summary, sharpe, sortino, max_drawdown


def test_performance_summary_basic():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    eq = pd.Series([100, 102, 101, 103, 104], index=dates)
    summary = performance_summary(eq)
    assert summary["total_return"] > 0
    assert "monthly_returns" in summary


def test_max_drawdown_negative():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    eq = pd.Series([100, 90, 80], index=dates)
    dd = max_drawdown(eq)
    assert dd < 0


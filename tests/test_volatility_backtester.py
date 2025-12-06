import pandas as pd

from src.volatility.volatility_backtester import VolatilityBacktester, VolBacktestConfig


def test_vol_backtester_runs_and_applies_signals():
    dates = pd.date_range("2023-01-01", periods=5, freq="D")
    signals = pd.Series([0, 1, 1, -1, 0], index=dates)

    # Build monotonic prices so returns are deterministic
    uvxy = pd.DataFrame({"Date": dates, "Close": [10, 10.5, 11.0, 11.5, 11.7]})
    svxy = pd.DataFrame({"Date": dates, "Close": [100, 101, 102, 103, 104]})

    backtester = VolatilityBacktester(VolBacktestConfig(cost_bps=0.0))
    metrics = backtester.run(signals, {"UVXY": uvxy, "SVXY": svxy})

    assert metrics["trades"] > 0
    assert metrics["final_value"] > 0
    assert metrics["period_days"] == 5


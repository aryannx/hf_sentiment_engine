import numpy as np  # type: ignore
import pandas as pd  # type: ignore

from src.intraday.intraday_backtester import IntradayBacktester
from src.intraday.intraday_signal_generator import IntradaySignalGenerator


def _mock_frame():
    rows = 8
    df = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows, freq="H"),
            "Close": np.linspace(100, 101, rows),
            "High": np.linspace(101, 102, rows),
            "Low": np.linspace(99, 100, rows),
            "Volume": np.linspace(1_000, 1_700, rows),
            "VOLUME_MA": np.full(rows, 1_100.0),
            "RSI": np.linspace(40, 10, rows),
            "BAND_DISTANCE": np.linspace(0.5, -3.0, rows),
            "BB_WIDTH_PCT": np.full(rows, 0.04),
            "REGIME": ["sideways"] * rows,
            "BB_MIDDLE": np.linspace(100, 100.5, rows),
        }
    )
    df["SLOW_K"] = [30, 25, 15, 10, 45, 18, 30, 40]
    df["SLOW_D"] = [35, 30, 20, 18, 30, 16, 18, 20]
    df["FAST_K"] = df["SLOW_K"]
    df["FAST_D"] = df["SLOW_D"]
    df.loc[4, "RSI"] = 12
    df.loc[4, "BAND_DISTANCE"] = -3.5
    return df


def test_intraday_signal_generator_flags_rare_setup():
    df = _mock_frame()
    generator = IntradaySignalGenerator()
    signals = generator.generate_signal(df, style="rare")
    assert signals.sum() > 0, "Expected at least one long setup"


def test_support_confirmation_blocks_signal_when_far():
    df = _mock_frame()
    generator = IntradaySignalGenerator()
    signals = generator.generate_signal(df, style="rare", confirmations=["support"], support_levels=[50])
    assert signals.sum() == 0

    near_level = df["Close"].iloc[4]
    signals = generator.generate_signal(
        df,
        style="rare",
        confirmations=["support"],
        support_levels=[near_level * (1 + 0.001)],
    )
    assert signals.sum() > 0


def test_intraday_backtester_produces_trade_log():
    df = _mock_frame()
    generator = IntradaySignalGenerator()
    signals = generator.generate_signal(df, style="rare")
    backtester = IntradayBacktester()
    metrics = backtester.run_backtest(df, signals=signals)
    assert "trades" in metrics
    if metrics["trade_count"]:
        first_trade = metrics["trades"][0]
        assert "return" in first_trade


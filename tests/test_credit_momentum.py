import numpy as np
import pandas as pd

from src.credit.credit_signal_generator import CreditSignalGenerator


def make_aligned_df():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    data = {
        "close_ig": np.linspace(100, 101, len(dates)),
        "close_hy": np.linspace(100, 105, len(dates)),  # HY trending up faster
    }
    df = pd.DataFrame(data, index=dates)
    df["ret_ig"] = df["close_ig"].pct_change()
    df["ret_hy"] = df["close_hy"].pct_change()
    df["hy_minus_ig_ret"] = df["ret_hy"] - df["ret_ig"]
    return df.dropna()


def test_momentum_ratio_triggers_long_hy():
    gen = CreditSignalGenerator()
    df = make_aligned_df()
    sentiment = pd.Series([0.1] * len(df), index=df.index)  # risk-on

    signals = gen.generate_signal(
        aligned_df=df,
        sentiment=sentiment,
        oas_df=None,
        strategy="momentum_ratio",
        momentum_window=3,
        momentum_threshold=0.0,
    )

    assert -1 in signals, "Expected long HY signal when HY momentum exceeds IG under risk-on"


def test_momentum_ratio_triggers_long_ig_on_risk_off():
    gen = CreditSignalGenerator()
    df = make_aligned_df()
    # Flip HY to be weaker than IG to create negative momentum_diff
    df["close_hy"] = np.linspace(100, 99, len(df))
    df["ret_hy"] = df["close_hy"].pct_change()
    df["hy_minus_ig_ret"] = df["ret_hy"] - df["ret_ig"]
    sentiment = pd.Series([-0.2] * len(df), index=df.index)  # risk-off

    signals = gen.generate_signal(
        aligned_df=df,
        sentiment=sentiment,
        oas_df=None,
        strategy="momentum_ratio",
        momentum_window=3,
        momentum_threshold=0.0,
    )

    # risk-off + negative momentum_diff should produce some +1 signals
    assert 1 in signals, "Expected long IG signal when HY momentum lags IG under risk-off"


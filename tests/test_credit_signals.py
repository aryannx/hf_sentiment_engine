import numpy as np
import pandas as pd

from src.credit.credit_signal_generator import CreditSignalGenerator


def make_aligned_df():
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    data = {
        "close_ig": [100, 101, 102, 103, 102, 101],
        "close_hy": [100, 99, 98, 97, 98, 99],
    }
    df = pd.DataFrame(data, index=dates)
    df["ret_ig"] = df["close_ig"].pct_change()
    df["ret_hy"] = df["close_hy"].pct_change()
    df["hy_minus_ig_ret"] = df["ret_hy"] - df["ret_ig"]
    return df.dropna()


def test_generate_signal_with_oas_percentile_filter():
    gen = CreditSignalGenerator()
    df = make_aligned_df()

    # Construct synthetic OAS with an extreme widening in the middle rows
    oas = pd.DataFrame(
        {
            "hy_oas": [300, 305, 450, 455, 310],
            "ig_oas": [150, 152, 160, 161, 155],
        },
        index=df.index,
    )
    oas["hy_ig_oas_spread"] = oas["hy_oas"] - oas["ig_oas"]

    # Sentiment flips risk-on around the widening period
    sentiment = pd.Series([0.0, 0.1, 0.2, 0.15, 0.0], index=df.index)

    signals = gen.generate_signal(
        aligned_df=df,
        sentiment=sentiment,
        oas_df=oas,
        sentiment_threshold=0.05,
        z_window=3,
        z_threshold=0.5,
        use_percentile_filter=True,
        lower_percentile=10.0,
        upper_percentile=90.0,
    )

    # Expect a short-IG/long-HY signal (-1) when spreads are wide + risk-on
    assert -1 in signals, "Expected at least one long-HY signal when OAS widens with risk-on sentiment"


def test_generate_signal_price_proxy_no_oas():
    gen = CreditSignalGenerator()
    df = make_aligned_df()

    # Risk-off sentiment should trigger long IG when price spread tightens
    sentiment = pd.Series([-0.2] * len(df), index=df.index)

    signals = gen.generate_signal(
        aligned_df=df,
        sentiment=sentiment,
        oas_df=None,
        sentiment_threshold=0.05,
        z_window=3,
        z_threshold=0.5,
        use_percentile_filter=False,
    )

    # With sustained risk-off, expect at least one +1 signal (long IG vs HY)
    assert 1 in signals, "Expected at least one long-IG signal using price-based proxy under risk-off"


def test_compute_pair_trade_returns_shapes_and_sign():
    gen = CreditSignalGenerator()
    df = make_aligned_df()

    # Alternate signals to produce both positive and negative legs
    signals = np.array([1, -1, 0, 1, -1], dtype=int)
    signals = np.insert(signals, 0, 0)  # align length after dropna
    signals = signals[1:]  # align with df length

    strat_ret = gen.compute_pair_trade_returns(df, signals, notional=1.0)

    assert len(strat_ret) == len(df)
    assert strat_ret.index.equals(df.index)
    # Should contain both positive and negative returns given alternating signals
    assert strat_ret.max() > 0 or strat_ret.min() < 0


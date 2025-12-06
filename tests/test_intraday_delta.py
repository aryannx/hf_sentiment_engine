import pandas as pd
import numpy as np

from src.intraday.intraday_signal_generator import IntradaySignalGenerator


def test_delta_filter_blocks_non_neutral():
    dates = pd.date_range("2023-01-01", periods=5, freq="H")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Close": [100, 99, 98, 97, 96],
            "RSI": [15, 15, 15, 15, 15],
            "BAND_DISTANCE": [-3, -3, -3, -3, -3],
            "SLOW_K": [10, 15, 30, 40, 50],
            "SLOW_D": [12, 14, 28, 38, 48],
            "REGIME": ["sideways"] * 5,
            "BB_WIDTH_PCT": [0.05] * 5,
            "EMA_SLOPE": [0.0] * 5,
            "Volume": [1000] * 5,
            "VOLUME_MA": [1000] * 5,
        }
    )
    delta_z = pd.Series([0.1, 0.2, 1.5, 0.1, 0.1], index=df.index)
    gen = IntradaySignalGenerator()
    sigs = gen.scan_for_setups(
        df,
        style="rare",
        confirmations=[],
        delta_z_series=delta_z,
        allow_breakout=False,
    )
    # Only indices where delta_z <= 0.75 should pass (0,1,3,4), index2 blocked
    assert 2 not in sigs.index


import pandas as pd

from src.volatility.volatility_signal_generator import (
    VolatilitySignalGenerator,
    VolSignalConfig,
)
from src.volatility.volatility_data_fetcher import TermStructureMetrics


def test_signal_long_on_backwardation_or_high_vix():
    gen = VolatilitySignalGenerator(VolSignalConfig(backwardation_ratio=1.01))
    metrics = TermStructureMetrics(front=18, second=17, ratio=1.058, slope=-0.055, contango=False)
    sig = gen.generate_signal_point(metrics, vix_spot=35.0)
    assert sig == 1


def test_signal_short_on_contango_and_low_vix():
    gen = VolatilitySignalGenerator(VolSignalConfig(contango_ratio=0.99))
    metrics = TermStructureMetrics(front=15, second=16, ratio=0.9375, slope=0.066, contango=True)
    sig = gen.generate_signal_point(metrics, vix_spot=17.0)
    assert sig == -1


def test_series_generation_aligns_dates():
    dates = pd.date_range("2023-01-01", periods=3, freq="D")
    ts_df = pd.DataFrame({"ratio": [1.05, 0.95, 1.0]}, index=dates)
    vix = pd.Series([32, 18, 22], index=dates)
    gen = VolatilitySignalGenerator()
    series = gen.generate_series(ts_df, vix)
    assert list(series) == [1, -1, 0]


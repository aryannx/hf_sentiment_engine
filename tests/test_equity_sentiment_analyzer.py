import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.equities.equity_sentiment_analyzer import EquitySentimentAnalyzer


def test_get_daily_sentiment_series_blends_sources(monkeypatch):
    analyzer = EquitySentimentAnalyzer()
    dates = [
        date(2024, 5, 1),
        date(2024, 5, 2),
        date(2024, 5, 3),
    ]

    def fake_finnhub(self, *_args, **_kwargs):
        return pd.Series([0.2, 0.4], index=dates[:2], name="finnhub")

    def fake_fmp(self, *_args, **_kwargs):
        return pd.Series([0.0, 0.6], index=dates[1:], name="fmp")

    def fake_eodhd(self, *_args, **_kwargs):
        return pd.Series([0.3], index=[dates[2]], name="eodhd")

    monkeypatch.setattr(EquitySentimentAnalyzer, "_finnhub_daily", fake_finnhub)
    monkeypatch.setattr(EquitySentimentAnalyzer, "_fmp_daily", fake_fmp)
    monkeypatch.setattr(EquitySentimentAnalyzer, "_eodhd_daily", fake_eodhd)

    series = analyzer.get_daily_sentiment_series("TEST", "2024-05-01", "2024-05-03")

    assert pytest.approx(series.loc[dates[0]]) == 0.2
    assert pytest.approx(series.loc[dates[1]]) == (0.4 + 0.0) / 2
    assert pytest.approx(series.loc[dates[2]]) == (0.6 + 0.3) / 2


def test_get_daily_sentiment_series_returns_empty_when_no_sources(monkeypatch):
    analyzer = EquitySentimentAnalyzer()

    def _empty(self, *_args, **_kwargs):
        return pd.Series(dtype=float)

    monkeypatch.setattr(EquitySentimentAnalyzer, "_finnhub_daily", _empty)
    monkeypatch.setattr(EquitySentimentAnalyzer, "_fmp_daily", _empty)
    monkeypatch.setattr(EquitySentimentAnalyzer, "_eodhd_daily", _empty)

    series = analyzer.get_daily_sentiment_series("TEST", "2024-05-01", "2024-05-03")
    assert series.empty


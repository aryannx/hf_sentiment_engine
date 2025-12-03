import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.equities import equity_data_fetcher
from src.equities.equity_data_fetcher import EquityDataFetcher


def test_add_indicators_generates_expected_columns():
    fetcher = EquityDataFetcher(use_curl_session=False)
    df = pd.DataFrame(
        {
            "Date": pd.date_range("2024-03-01", periods=5, freq="D"),
            "Open": [100, 101, 102, 103, 104],
            "High": [101, 102, 103, 104, 105],
            "Low": [99, 100, 101, 102, 103],
            "Close": [100, 101, 102, 103, 104],
            "Volume": np.arange(5),
        }
    )

    enriched = fetcher._add_indicators(df)

    for col in ("SMA_20", "SMA_50", "RSI", "ATR"):
        assert col in enriched.columns
    assert enriched["RSI"].between(0, 100).all()
    assert (enriched["ATR"] >= 0).all()


def test_fetch_stock_data_handles_multiindex(monkeypatch):
    def fake_download(*args, **kwargs):
        idx = pd.date_range("2024-04-01", periods=3, freq="D")
        data = pd.DataFrame(
            {
                ("Open", ""): [100, 101, 102],
                ("High", ""): [101, 102, 103],
                ("Low", ""): [99, 100, 101],
                ("Close", ""): [100, 101, 102],
                ("Volume", ""): [1_000, 1_100, 1_200],
            },
            index=idx,
        )
        data.index.name = "Date"
        return data

    monkeypatch.setattr(equity_data_fetcher.yf, "download", fake_download)

    fetcher = EquityDataFetcher(use_curl_session=False)
    df = fetcher.fetch_stock_data("TEST", period="1mo", add_indicators=True)

    assert not df.empty
    assert "SMA_20" in df.columns
    assert "ticker" in df.columns


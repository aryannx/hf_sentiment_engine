from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from exec.data_sources import compute_vwap_from_bars, estimate_adv_from_bars, estimate_spread_from_quotes

try:
    import finnhub  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    finnhub = None


def _client():
    if finnhub is None:
        raise RuntimeError("finnhub not installed; pip install finnhub-python")
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        raise RuntimeError("FINNHUB_API_KEY not set")
    return finnhub.Client(api_key=api_key)


def finnhub_intraday_bars(ticker: str, resolution: str = "5", lookback_days: int = 5) -> pd.DataFrame:
    client = _client()
    end = int(datetime.utcnow().timestamp())
    start = end - lookback_days * 24 * 3600
    res = client.stock_candles(ticker, resolution, start, end)
    if res.get("s") != "ok":  # type: ignore
        return pd.DataFrame()
    return pd.DataFrame({"Close": res["c"], "Volume": res["v"]})  # type: ignore


def finnhub_quote(ticker: str) -> pd.DataFrame:
    client = _client()
    q = client.quote(ticker)
    return pd.DataFrame([{"bid": q.get("b"), "ask": q.get("a")}])


def adv_lookup_finnhub(ticker: str) -> float:
    bars = finnhub_intraday_bars(ticker, resolution="5", lookback_days=5)
    return estimate_adv_from_bars(bars)


def spread_lookup_finnhub(ticker: str) -> float:
    quotes = finnhub_quote(ticker)
    return estimate_spread_from_quotes(quotes, window=1)


def vwap_from_finnhub(ticker: str) -> float:
    bars = finnhub_intraday_bars(ticker, resolution="5", lookback_days=1)
    return compute_vwap_from_bars(bars)


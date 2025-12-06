from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from exec.data_sources import compute_vwap_from_bars, estimate_adv_from_bars, estimate_spread_from_quotes

try:
    from polygon import RESTClient  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    RESTClient = None


def _client() -> "RESTClient":
    if RESTClient is None:
        raise RuntimeError("polygon-api-client not installed; pip install polygon-api-client")
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY not set")
    return RESTClient(api_key)


def polygon_intraday_bars(ticker: str, timespan: str = "minute", lookback_days: int = 5) -> pd.DataFrame:
    client = _client()
    end = datetime.utcnow().date()
    start = end - timedelta(days=lookback_days)
    rows = []
    try:
        aggs = client.list_aggs(ticker, 1, timespan, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        for a in aggs:
            rows.append({"Close": a.close, "Volume": a.volume})
    except Exception as exc:  # pragma: no cover - network dependent
        raise RuntimeError(f"Polygon aggregation failed: {exc}") from exc
    return pd.DataFrame(rows)


def polygon_quotes(ticker: str, limit: int = 500) -> pd.DataFrame:
    client = _client()
    rows = []
    try:
        quotes = client.list_quotes(ticker, limit=limit)
        for q in quotes:
            rows.append({"bid": q.bid_price, "ask": q.ask_price})
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Polygon quotes failed: {exc}") from exc
    return pd.DataFrame(rows)


def adv_lookup_polygon(ticker: str) -> float:
    bars = polygon_intraday_bars(ticker, timespan="minute", lookback_days=5)
    return estimate_adv_from_bars(bars)


def spread_lookup_polygon(ticker: str) -> float:
    quotes = polygon_quotes(ticker, limit=500)
    return estimate_spread_from_quotes(quotes, window=100)


def vwap_from_polygon_minutes(ticker: str) -> float:
    bars = polygon_intraday_bars(ticker, timespan="minute", lookback_days=1)
    return compute_vwap_from_bars(bars)


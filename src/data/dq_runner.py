from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf

from src.core.notifier import notify
from src.data.cross_source import cross_source_price_check

try:
    from polygon import RESTClient  # type: ignore
except ImportError:  # pragma: no cover
    RESTClient = None

try:
    import finnhub  # type: ignore
except ImportError:  # pragma: no cover
    finnhub = None


def _fetch_yf_close(ticker: str, days: int = 5) -> Optional[float]:
    df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])


def _fetch_polygon_close(ticker: str, days: int = 5) -> Optional[float]:
    if RESTClient is None:
        return None
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        return None
    client = RESTClient(api_key)
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    try:
        aggs = client.list_aggs(ticker, 1, "day", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        closes = [a.close for a in aggs]
        return float(closes[-1]) if closes else None
    except Exception:
        return None


def _fetch_finnhub_close(ticker: str, days: int = 5) -> Optional[float]:
    if finnhub is None:
        return None
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return None
    client = finnhub.Client(api_key=api_key)
    end = int(datetime.utcnow().timestamp())
    start = end - days * 24 * 3600
    try:
        res = client.stock_candles(ticker, "D", start, end)
        if res.get("s") != "ok":
            return None
        return float(res["c"][-1])
    except Exception:
        return None


def run_checks(tickers: List[str], tolerance: float = 0.01) -> None:
    for t in tickers:
        primary = _fetch_yf_close(t)
        secondary = _fetch_polygon_close(t)
        if secondary is None:
            secondary = _fetch_finnhub_close(t)
        if primary is None or secondary is None:
            notify(f"DQ: missing price for {t}", level="warn")
            continue
        df = pd.DataFrame({"primary": [primary], "secondary": [secondary]}, index=[t])
        msg = cross_source_price_check(primary_source="yf", primary_df=df[["primary"]], secondary_df=df[["secondary"]], tolerance=tolerance)
        if msg:
            notify(f"DQ: price diff {t} -> {msg}", level="warn")


def main() -> None:
    tickers_env = os.getenv("DQ_TICKERS")
    tickers = [t.strip().upper() for t in tickers_env.split(",")] if tickers_env else ["AAPL", "MSFT", "SPY"]
    tolerance = float(os.getenv("DQ_TOLERANCE", "0.01"))
    run_checks(tickers, tolerance=tolerance)


if __name__ == "__main__":
    main()


"""
Utilities for retrieving intraday price data and computing indicator stacks that
the intraday module relies on (RSI, Bollinger Bands, stochastic oscillators,
band distance metrics, etc.).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import importlib
import requests


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = upper - lower
    width_pct = width / mid.replace(0, np.nan)
    band_distance = (series - mid) / std.replace(0, np.nan)
    return pd.DataFrame(
        {
            "BB_MIDDLE": mid,
            "BB_UPPER": upper,
            "BB_LOWER": lower,
            "BB_WIDTH": width,
            "BB_WIDTH_PCT": width_pct,
            "BAND_DISTANCE": band_distance,
        }
    )


def _stochastic(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    lowest_low = df["Low"].rolling(window, min_periods=window).min()
    highest_high = df["High"].rolling(window, min_periods=window).max()
    range_span = (highest_high - lowest_low).replace(0, np.nan)
    fast_k = (df["Close"] - lowest_low) / range_span * 100
    fast_d = fast_k.rolling(3, min_periods=3).mean()
    slow_k = fast_d
    slow_d = slow_k.rolling(3, min_periods=3).mean()
    return pd.DataFrame(
        {
            "FAST_K": fast_k,
            "FAST_D": fast_d,
            "SLOW_K": slow_k,
            "SLOW_D": slow_d,
        }
    )


@dataclass
class IntradayDataFetcher:
    """
    Wrapper around yfinance downloads with indicator engineering baked in.

    Parameters
    ----------
    use_curl_session : bool
        Whether to attempt curl_cffi impersonation for more resilient downloads.
    """

    use_curl_session: bool = True

    def fetch(
        self,
        ticker: str,
        *,
        period: str = "180d",
        interval: str = "1h",
        add_indicators: bool = True,
        provider: str = "yfinance",
    ) -> pd.DataFrame:
        """Fetch intraday/short-horizon bars and enrich with features."""
        if provider == "yfinance":
            data = self._fetch_from_yfinance(ticker, period, interval)
        elif provider == "finnhub":
            data = self._fetch_from_finnhub(ticker, period, interval)
        elif provider == "polygon":
            data = self._fetch_from_polygon(ticker, period, interval)
        else:
            raise ValueError(f"Unsupported provider '{provider}'.")

        if data.empty:
            return data

        if add_indicators:
            data = self._add_indicators(data.copy())

        data["ticker"] = ticker
        return data

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["RSI"] = _rsi(df["Close"])
        boll = _bollinger(df["Close"])
        stoch = _stochastic(df)

        df = pd.concat([df, boll, stoch], axis=1)

        df["EMA_FAST"] = df["Close"].ewm(span=21, adjust=False).mean()
        df["EMA_SLOW"] = df["Close"].ewm(span=55, adjust=False).mean()
        df["EMA_SLOPE"] = df["EMA_FAST"] - df["EMA_FAST"].shift(3)
        df["VOLUME_MA"] = df["Volume"].rolling(30, min_periods=5).mean()

        df["REGIME"] = np.where(
            (df["BB_WIDTH_PCT"] < 0.06) & (df["EMA_SLOPE"].abs() < 0.15),
            "sideways",
            "trending",
        )

        # Cumulative delta proxy: price change * volume, with z-score gate
        price_change = df["Close"].diff().fillna(0.0)
        df["CUM_DELTA_RAW"] = (price_change * df["Volume"]).fillna(0.0)
        window = 50
        mean = df["CUM_DELTA_RAW"].rolling(window, min_periods=10).mean()
        std = df["CUM_DELTA_RAW"].rolling(window, min_periods=10).std().replace(0, np.nan)
        df["CUM_DELTA_Z"] = (df["CUM_DELTA_RAW"] - mean) / std

        return df.ffill()

    def _fetch_from_yfinance(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        yf = self._load_yfinance()
        session = None
        if self.use_curl_session:
            session = self._maybe_curl_session()

        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            session=session,
        )

        if data.empty:
            return data

        data = data.reset_index().rename(columns={"index": "Date"})
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data

    def _fetch_from_finnhub(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        token = self._get_env_key("FINNHUB_API_KEY")
        resolution = self._interval_to_finnhub(interval)
        start, end = self._period_to_range(period)

        params = {
            "symbol": ticker,
            "resolution": resolution,
            "from": int(start.timestamp()),
            "to": int(end.timestamp()),
            "token": token,
        }
        resp = requests.get("https://finnhub.io/api/v1/stock/candle", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("s") != "ok":
            raise RuntimeError(f"Finnhub returned status {data.get('s')} for {ticker}")

        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(data["t"], unit="s", utc=True),
                "Open": data["o"],
                "High": data["h"],
                "Low": data["l"],
                "Close": data["c"],
                "Volume": data["v"],
            }
        )
        return df

    def _fetch_from_polygon(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        token = self._get_env_key("POLYGON_API_KEY")
        multiplier, timespan = self._interval_to_polygon(interval)
        start, end = self._period_to_range(period)

        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start.date()}/{end.date()}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": token,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results")
        if not results:
            raise RuntimeError(f"Polygon returned no data for {ticker}")

        df = pd.DataFrame(results)
        df = df.rename(
            columns={
                "t": "Date",
                "o": "Open",
                "h": "High",
                "l": "Low",
                "c": "Close",
                "v": "Volume",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"], unit="ms", utc=True)
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    @staticmethod
    def _period_to_range(period: str) -> Tuple[datetime, datetime]:
        end = datetime.now(timezone.utc)
        period = period.lower()
        if period.endswith("d"):
            value = int(period[:-1])
            delta = timedelta(days=value)
        elif period.endswith("mo"):
            value = int(period[:-2])
            delta = timedelta(days=value * 30)
        elif period.endswith("y"):
            value = int(period[:-1])
            delta = timedelta(days=value * 365)
        else:
            raise ValueError(f"Unsupported period format '{period}'")
        start = end - delta
        return start, end

    @staticmethod
    def _interval_to_finnhub(interval: str) -> str:
        mapping = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "4h": "240",
        }
        if interval not in mapping:
            raise ValueError(f"Finnhub unsupported interval '{interval}'")
        return mapping[interval]

    @staticmethod
    def _interval_to_polygon(interval: str) -> Tuple[int, str]:
        mapping = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "15m": (15, "minute"),
            "30m": (30, "minute"),
            "1h": (1, "hour"),
        }
        if interval not in mapping:
            raise ValueError(f"Polygon unsupported interval '{interval}'")
        return mapping[interval]

    @staticmethod
    def _get_env_key(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"{name} environment variable is required for this provider.")
        return value

    @staticmethod
    def _load_yfinance():
        try:
            return importlib.import_module("yfinance")
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "yfinance is required for intraday fetching. Install it via pip."
            ) from exc

    @staticmethod
    def _maybe_curl_session():
        try:
            curl_requests = importlib.import_module("curl_cffi.requests")
            return curl_requests.Session(impersonate="chrome110")
        except Exception:
            return None


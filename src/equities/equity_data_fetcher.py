# src/equities/equity_data_fetcher.py
"""
Equity price data fetcher with technical indicators
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Iterable
import numpy as np
import pandas as pd
import yfinance as yf
import requests

import warnings
from src.data.validators import run_validations
from src.data.lineage import log_lineage, checksum_df

# Suppress yfinance future warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")


class EquityDataFetcher:
    """Fetch equity price data and compute technical indicators with provider fallbacks."""

    def __init__(self, use_curl_session=True, providers: Optional[Iterable[str]] = None):
        self.use_curl_session = use_curl_session
        # Default priority: low-latency paid feeds first, yfinance last-resort
        self.providers = list(providers) if providers else ["polygon", "finnhub", "yfinance"]

    def fetch_stock_data(self, ticker, period="3mo", interval="1d", add_indicators=True):
        """
        Fetch stock data with provider priority (Polygon -> Finnhub -> yfinance).

        Args:
            ticker (str): Stock symbol (e.g., 'AAPL')
            period (str): Time period ('3mo', '1y')
            interval (str): Candle interval ('1d', '1h')
            add_indicators (bool): Whether to add SMA, RSI, ATR

        Returns:
            pd.DataFrame: Data with indicators
        """
        last_err = None
        for provider in self.providers:
            try:
                if provider == "polygon":
                    data = self._fetch_polygon(ticker, period, interval)
                elif provider == "finnhub":
                    data = self._fetch_finnhub(ticker, period, interval)
                elif provider == "yfinance":
                    data = self._fetch_yfinance(ticker, period, interval)
                else:
                    continue

                if data is None or data.empty:
                    continue

                data["ticker"] = ticker
                data.ffill(inplace=True)

                if add_indicators:
                    data = self._add_indicators(data)

                dq_msgs = run_validations(data, required_cols=["Date", "Close"])
                if dq_msgs:
                    print("⚠️ Data quality warnings:", "; ".join(dq_msgs))
                log_lineage(
                    provider,
                    {"ticker": ticker, "period": period, "interval": interval, "dq": dq_msgs, "checksum": checksum_df(data)},
                )
                return data.dropna()
            except Exception as e:
                last_err = e
                continue

        if last_err:
            print(f"Error fetching {ticker} (all providers failed): {last_err}")
        else:
            print(f"Warning: No data found for {ticker} across providers {self.providers}")
        return pd.DataFrame()

    @staticmethod
    def _add_indicators(df_in):
        """
        Compute technical indicators (SMA, RSI, ATR)
        Using explicit parameter name 'df_in' to avoid confusion
        """
        df = df_in.copy()

        # Simple Moving Averages
        df['SMA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['SMA_50'] = df['Close'].rolling(window=50, min_periods=1).mean()

        # RSI Calculation
        delta = df['Close'].diff()
        gain = delta.clip(lower=0).rolling(window=14, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14, min_periods=1).mean()

        # Avoid division by zero
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = 100 - (100 / (1 + rs))
        df['RSI'] = df['RSI'].fillna(50)

        # ATR Calculation
        high = df['High']
        low = df['Low']
        close = df['Close']
        prev_close = close.shift()

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(window=14, min_periods=1).mean()

        return df

    # --- Provider backends ---
    def _fetch_yfinance(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        # Try to use curl_cffi for stability (avoids 403 errors)
        if self.use_curl_session:
            try:
                from curl_cffi import requests as curl_requests

                session = curl_requests.Session(impersonate="chrome110")
                data = yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    session=session,
                    auto_adjust=False,
                )
            except ImportError:
                data = yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=False,
                )
        else:
            data = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
            )

        if data is None or data.empty:
            return pd.DataFrame()
        data = data.reset_index()
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data

    def _fetch_finnhub(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        token = os.getenv("FINNHUB_API_KEY")
        if not token:
            return pd.DataFrame()
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
            return pd.DataFrame()
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

    def _fetch_polygon(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        token = os.getenv("POLYGON_API_KEY")
        if not token:
            return pd.DataFrame()
        multiplier, timespan = self._interval_to_polygon(interval)
        start, end = self._period_to_range(period)
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start.date()}/{end.date()}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": token}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results)
        df["Date"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    # --- Helpers ---
    @staticmethod
    def _period_to_range(period: str) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        if period.endswith("y"):
            years = int(period[:-1])
            start = now - timedelta(days=365 * years)
        elif period.endswith("mo"):
            months = int(period[:-2])
            start = now - timedelta(days=30 * months)
        elif period.endswith("d"):
            days = int(period[:-1])
            start = now - timedelta(days=days)
        else:
            start = now - timedelta(days=180)
        return start, now

    @staticmethod
    def _interval_to_finnhub(interval: str) -> str:
        mapping = {
            "1d": "D",
            "1h": "60",
            "30m": "30",
            "15m": "15",
            "5m": "5",
            "1m": "1",
        }
        return mapping.get(interval, "D")

    @staticmethod
    def _interval_to_polygon(interval: str) -> tuple[int, str]:
        mapping = {
            "1d": (1, "day"),
            "1h": (60, "minute"),
            "30m": (30, "minute"),
            "15m": (15, "minute"),
            "5m": (5, "minute"),
            "1m": (1, "minute"),
        }
        return mapping.get(interval, (1, "day"))


if __name__ == "__main__":
    # Simple test block
    fetcher = EquityDataFetcher()
    print("Fetching AAPL data...")
    data = fetcher.fetch_stock_data("AAPL", period="1mo")

    if not data.empty:
        print("Success! Data shape:", data.shape)
        print(data[['Date', 'Close', 'SMA_20', 'RSI']].tail())
    else:
        print("Failed to fetch data. ❌")

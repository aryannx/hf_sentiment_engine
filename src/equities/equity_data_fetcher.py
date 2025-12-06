# src/equities/equity_data_fetcher.py
"""
Equity price data fetcher with technical indicators
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
import yfinance as yf

import warnings
from src.data.validators import run_validations
from src.data.lineage import log_lineage, checksum_df

# Suppress yfinance future warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")


class EquityDataFetcher:
    """Fetch equity price data and compute technical indicators"""

    def __init__(self, use_curl_session=True):
        self.use_curl_session = use_curl_session

    def fetch_stock_data(self, ticker, period="3mo", interval="1d", add_indicators=True):
        """
        Fetch stock data from yfinance

        Args:
            ticker (str): Stock symbol (e.g., 'AAPL')
            period (str): Time period ('3mo', '1y')
            interval (str): Candle interval ('1d', '1h')
            add_indicators (bool): Whether to add SMA, RSI, ATR

        Returns:
            pd.DataFrame: Data with indicators
        """
        try:
            # Try to use curl_cffi for stability (avoids 403 errors)
            if self.use_curl_session:
                try:
                    from curl_cffi import requests
                    session = requests.Session(impersonate="chrome110")
                    data = yf.download(
                        ticker,
                        period=period,
                        interval=interval,
                        progress=False,
                        session=session,
                        auto_adjust=False
                    )
                except ImportError:
                    print("Note: curl_cffi not installed. Using default requests.")
                    data = yf.download(
                        ticker,
                        period=period,
                        interval=interval,
                        progress=False,
                        auto_adjust=False
                    )
            else:
                data = yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=False
                )

            if data.empty:
                print(f"Warning: No data found for {ticker}")
                return pd.DataFrame()

            # Clean up data structure
            data = data.reset_index()

            # Handle MultiIndex columns if present (yfinance update feature)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            data['ticker'] = ticker
            data.ffill(inplace=True)

            # Add technical indicators if requested
            if add_indicators:
                data = self._add_indicators(data)

            # Data quality checks
            dq_msgs = run_validations(data, required_cols=["Date", "Close"])
            if dq_msgs:
                print("⚠️ Data quality warnings:", "; ".join(dq_msgs))
            log_lineage(
                "yfinance",
                {"ticker": ticker, "period": period, "interval": interval, "dq": dq_msgs, "checksum": checksum_df(data)},
            )

            return data.dropna()

        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
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

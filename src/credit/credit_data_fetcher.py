# src/credit/credit_data_fetcher.py
"""
CreditDataFetcher: fetch and align LQD/HYG prices and OAS spreads.

Uses:
    - yfinance for LQD/HYG ETF prices
    - FRED API for IG/HY OAS spreads
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import yfinance as yf
from pandas_datareader import data as pdr

from src.core.base_data_fetcher import BaseDataFetcher


class CreditDataFetcher(BaseDataFetcher):
    """
    Fetch IG (LQD) and HY (HYG) ETF prices + OAS spreads from FRED.
    """

    def __init__(self, ig_ticker: str = "LQD", hy_ticker: str = "HYG"):
        self.ig_ticker = ig_ticker
        self.hy_ticker = hy_ticker

    def fetch_ig_hy_pair(
        self, period: str = "1y", interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch LQD and HYG ETF price data.

        Returns
        -------
        dict
            {"LQD": DataFrame, "HYG": DataFrame}
        """
        print(f"📊 Fetching {self.ig_ticker}/{self.hy_ticker} prices (period={period}, interval={interval})...")

        ig = yf.download(self.ig_ticker, period=period, interval=interval, progress=False)
        hy = yf.download(self.hy_ticker, period=period, interval=interval, progress=False)

        ig["Date"] = ig.index
        hy["Date"] = hy.index

        return {self.ig_ticker: ig, self.hy_ticker: hy}

    def fetch_oas_pair(
        self, start: str, end: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch IG OAS and HY OAS from FRED.

        Returns
        -------
        DataFrame or None
            Columns: [Date, ig_oas, hy_oas, hy_ig_oas_spread]
        """
        try:
            print(f"📈 Fetching OAS spreads from FRED ({start} → {end})...")

            ig_oas_ticker = "BAMLH0A0IG"
            hy_oas_ticker = "BAMLH0A0HYM2"

            ig_oas = pdr.get_data_fred(ig_oas_ticker, start=start, end=end)
            hy_oas = pdr.get_data_fred(hy_oas_ticker, start=start, end=end)

            ig_oas.columns = ["ig_oas"]
            hy_oas.columns = ["hy_oas"]

            oas_df = pd.concat([ig_oas, hy_oas], axis=1)
            oas_df["hy_ig_oas_spread"] = oas_df["hy_oas"] - oas_df["ig_oas"]

            oas_df = oas_df.fillna(method="ffill").fillna(method="bfill")

            oas_df["Date"] = oas_df.index
            print(f"✅ Fetched {len(oas_df)} OAS records")
            return oas_df

        except Exception as e:
            print(f"[WARN] OAS fetch failed: {e}. Proceeding with price-based spreads.")
            return None

    def fetch_long_hy_oas(
        self, start: str = "2015-01-01", end: Optional[str] = None
    ) -> pd.Series:
        """
        Fetch a long history of HY OAS (e.g., 10 years) for percentile calculations.
        """
        try:
            hy_oas_ticker = "BAMLH0A0HYM2"
            hy_oas = pdr.get_data_fred(hy_oas_ticker, start=start, end=end)
            hy_oas.columns = ["hy_oas"]
            return hy_oas["hy_oas"].dropna()
        except Exception as e:
            print(f"[WARN] Long HY OAS fetch failed: {e}")
            return pd.Series(dtype=float)

    @staticmethod
    def align_ig_hy(
        ig_df: pd.DataFrame, hy_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Align LQD and HYG price data on trading dates, compute returns & HY-IG spread proxy.
        """
        if "Date" in ig_df.columns and "Date" in hy_df.columns:
            ig_df = ig_df.set_index("Date")
            hy_df = hy_df.set_index("Date")

        ig_close = ig_df["Close"].dropna()
        hy_close = hy_df["Close"].dropna()

        aligned = pd.DataFrame(
            {"close_ig": ig_close, "close_hy": hy_close}, index=ig_close.index
        )
        aligned = aligned.dropna()

        aligned["ret_ig"] = aligned["close_ig"].pct_change()
        aligned["ret_hy"] = aligned["close_hy"].pct_change()
        aligned["hy_minus_ig_ret"] = aligned["ret_hy"] - aligned["ret_ig"]

        return aligned


if __name__ == "__main__":
    fetcher = CreditDataFetcher()
    etfs = fetcher.fetch_ig_hy_pair(period="1y")
    aligned = CreditDataFetcher.align_ig_hy(etfs["LQD"], etfs["HYG"])
    print(aligned.head())

    oas = fetcher.fetch_oas_pair(
        start=aligned.index.min().strftime("%Y-%m-%d"),
        end=aligned.index.max().strftime("%Y-%m-%d"),
    )
    print(oas.head() if oas is not None else "No OAS")

    long_hy_oas = fetcher.fetch_long_hy_oas()
    print(long_hy_oas.tail())

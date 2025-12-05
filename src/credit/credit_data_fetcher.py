# src/credit/credit_data_fetcher.py
"""
CreditDataFetcher: fetch and align LQD/HYG prices and OAS spreads.

Uses:
    - yfinance for LQD/HYG ETF prices
    - FRED API for IG/HY OAS spreads
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from dotenv import load_dotenv
import pandas as pd
import requests
import yfinance as yf
from pandas_datareader import data as pdr
from src.data.validators import run_validations
from src.data.lineage import log_lineage, checksum_df

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from src.core.base_data_fetcher import BaseDataFetcher


class CreditDataFetcher(BaseDataFetcher):
    """
    Fetch IG (LQD) and HY (HYG) ETF prices + OAS spreads from FRED.
    """

    def __init__(
        self,
        ig_ticker: str = "LQD",
        hy_ticker: str = "HYG",
        ig_oas_series_id: str = "BAMLC0A0CM",   # ICE BofA US Corp Master OAS
        hy_oas_series_id: str = "BAMLH0A0HYM2",  # ICE BofA US High Yield OAS
        cache_path: Optional[str | Path] = None,
        use_curl_session: bool = True,
    ):
        self.ig_ticker = ig_ticker
        self.hy_ticker = hy_ticker
        self.ig_oas_series_id = ig_oas_series_id
        self.hy_oas_series_id = hy_oas_series_id
        # Default cache lives under data/raw (gitignored)
        self.cache_path = Path(cache_path) if cache_path else Path("data/raw/fred_oas.pkl")
        self.use_curl_session = use_curl_session
        self.polygon_key = os.getenv("POLYGON_API_KEY")
        self.fred_key = os.getenv("FRED_API_KEY")

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
        if self.polygon_key:
            print("🔑 Polygon key detected; will try Polygon before yfinance.")
        else:
            print("ℹ️ POLYGON_API_KEY not set; using yfinance only.")

        ig = self._download_prices(self.ig_ticker, period, interval)
        hy = self._download_prices(self.hy_ticker, period, interval)

        if (ig is None or ig.empty) or (hy is None or hy.empty):
            return {"LQD": pd.DataFrame(), "HYG": pd.DataFrame()}

        ig["Date"] = ig.index
        hy["Date"] = hy.index

        # Data quality + lineage
        for label, df in (("ig", ig), ("hy", hy)):
            dq_msgs = run_validations(df.reset_index(), required_cols=["Date", "Close"])
            log_lineage(
                f"yfinance_{label}",
                {
                    "ticker": self.ig_ticker if label == "ig" else self.hy_ticker,
                    "period": period,
                    "interval": interval,
                    "dq": dq_msgs,
                    "checksum": checksum_df(df.reset_index()),
                },
            )

        return {self.ig_ticker: ig, self.hy_ticker: hy}

    def fetch_oas_pair(
        self,
        start: str,
        end: str,
        use_cache: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch IG OAS and HY OAS from FRED.

        Returns
        -------
        DataFrame or None
            Columns: [Date, ig_oas, hy_oas, hy_ig_oas_spread]
        """
        try:
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)

            if use_cache:
                cached = self._load_cached_oas()
                if cached is not None:
                    sliced = cached.loc[(cached.index >= start_dt) & (cached.index <= end_dt)]
                    if not sliced.empty and sliced.index.min() <= start_dt and sliced.index.max() >= end_dt:
                        print(f"📦 Using cached OAS ({len(sliced)} rows) from {self.cache_path}")
                        sliced = sliced.copy()
                        sliced["Date"] = sliced.index
                        return sliced

            print(f"📈 Fetching OAS spreads from FRED ({start} → {end})...")

            ig_oas = self._fetch_fred_series(self.ig_oas_series_id, start, end)
            hy_oas = self._fetch_fred_series(self.hy_oas_series_id, start, end)

            ig_oas.columns = ["ig_oas"]
            hy_oas.columns = ["hy_oas"]

            oas_df = pd.concat([ig_oas, hy_oas], axis=1)
            oas_df["hy_ig_oas_spread"] = oas_df["hy_oas"] - oas_df["ig_oas"]

            oas_df = oas_df.fillna(method="ffill").fillna(method="bfill")

            oas_df["Date"] = oas_df.index
            print(f"✅ Fetched {len(oas_df)} OAS records")

            if use_cache and not oas_df.empty:
                self._save_oas_cache(oas_df)

            return oas_df

        except Exception as e:
            print(f"[WARN] OAS fetch failed: {e}. Proceeding with price-based spreads.")
            return None

    def fetch_long_hy_oas(
        self,
        start: str = "2015-01-01",
        end: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.Series:
        """
        Fetch a long history of HY OAS (e.g., 10 years) for percentile calculations.
        """
        try:
            if use_cache:
                cached = self._load_cached_oas()
                if cached is not None and "hy_oas" in cached.columns:
                    sliced = cached.copy()
                    start_dt = pd.to_datetime(start)
                    end_dt = pd.to_datetime(end) if end else None
                    if start_dt is not None:
                        sliced = sliced[sliced.index >= start_dt]
                    if end_dt is not None:
                        sliced = sliced[sliced.index <= end_dt]
                    if not sliced.empty:
                        return sliced["hy_oas"].dropna()

            hy_oas = self._fetch_fred_series(self.hy_oas_series_id, start, end)
            hy_oas.columns = ["hy_oas"]
            series = hy_oas["hy_oas"].dropna()

            if use_cache and not series.empty:
                # Merge with cache if present
                df = series.to_frame()
                df["ig_oas"] = pd.NA  # placeholder to keep schema consistent
                df["hy_ig_oas_spread"] = pd.NA
                df["Date"] = df.index
                self._save_oas_cache(df, merge=True)

            return series
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

    def _load_cached_oas(self) -> Optional[pd.DataFrame]:
        try:
            if not self.cache_path.is_file():
                return None
            df = pd.read_pickle(self.cache_path)
            if "Date" in df.columns:
                df = df.set_index("Date")
            df.index = pd.to_datetime(df.index)
            return df.sort_index()
        except Exception as e:
            print(f"[WARN] Failed to read OAS cache {self.cache_path}: {e}")
            return None

    def _save_oas_cache(self, df: pd.DataFrame, merge: bool = False) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            df_to_save = df.copy()
            if "Date" in df_to_save.columns:
                df_to_save = df_to_save.set_index("Date")
            if merge and self.cache_path.is_file():
                existing = self._load_cached_oas()
                if existing is not None:
                    df_to_save = pd.concat([existing, df_to_save]).sort_index()
            df_to_save.to_pickle(self.cache_path)
            print(f"💾 Saved OAS cache → {self.cache_path}")
        except Exception as e:
            print(f"[WARN] Failed to save OAS cache {self.cache_path}: {e}")

    def _download_prices(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        """
        Robust download preferring Polygon (if API key present), else yfinance.
        """
        # Try Polygon first if key is available and interval is daily
        if self.polygon_key and interval == "1d":
            poly = self._download_polygon_daily(ticker, period)
            if poly is not None and not poly.empty:
                return poly

        # Fallback to yfinance
        return self._download_yfinance(ticker, period, interval)

    def _download_polygon_daily(self, ticker: str, period: str) -> Optional[pd.DataFrame]:
        try:
            start_date, end_date = self._period_to_dates(period)
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
            params = {"adjusted": "true", "limit": 50000, "apiKey": self.polygon_key}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"[WARN] Polygon fetch failed for {ticker}: HTTP {resp.status_code} resp={resp.text[:200]}")
                return None
            data = resp.json()
            results = data.get("results") or []
            if not results:
                print(f"[WARN] Polygon returned empty results for {ticker}; payload={str(data)[:200]}")
                return None

            rows = []
            for r in results:
                ts = pd.to_datetime(r["t"], unit="ms")
                rows.append(
                    {
                        "Date": ts,
                        "Open": r["o"],
                        "High": r["h"],
                        "Low": r["l"],
                        "Close": r["c"],
                        "Adj Close": r["c"],
                        "Volume": r.get("v", 0),
                    }
                )
            df = pd.DataFrame(rows).set_index("Date").sort_index()
            return df
        except Exception as e:
            print(f"[WARN] Polygon download failed for {ticker}: {e}")
            return None

    @staticmethod
    def _period_to_dates(period: str) -> tuple[str, str]:
        """
        Convert yfinance-style period (e.g., '6mo', '1y') to start/end YYYY-MM-DD.
        """
        end = datetime.utcnow()
        if period.endswith("mo"):
            months = int(period.replace("mo", ""))
            start = end - pd.DateOffset(months=months)
        elif period.endswith("y"):
            years = int(period.replace("y", ""))
            start = end - pd.DateOffset(years=years)
        else:
            # default 1y
            start = end - pd.DateOffset(years=1)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def _download_yfinance(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        last_error: Optional[Exception] = None
        for attempt, use_curl in enumerate([self.use_curl_session, False], start=1):
            try:
                session = None
                if use_curl:
                    try:
                        from curl_cffi import requests as cffi_requests

                        session = cffi_requests.Session(impersonate="chrome110")
                    except ImportError:
                        session = None

                df = yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    session=session,
                    auto_adjust=False,
                )
                if df is not None and not df.empty:
                    return df
            except Exception as exc:
                last_error = exc
                continue

        msg = f"[WARN] Failed to download {ticker} via yfinance"
        if last_error:
            msg += f": {last_error}"
        print(msg)
        return pd.DataFrame()

    def _fetch_fred_series(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        """
        Fetch a single FRED series using fredapi if available and key present,
        otherwise fall back to pandas_datareader.
        """
        # Try fredapi if key exists
        if self.fred_key:
            try:
                from fredapi import Fred

                fred = Fred(api_key=self.fred_key)
                data = fred.get_series(series_id, observation_start=start, observation_end=end)
                df = data.to_frame(name=series_id)
                df.index = pd.to_datetime(df.index)
                return df
            except Exception as e:
                print(f"[WARN] fredapi fetch failed for {series_id}: {e}")

        # Fallback to pandas_datareader
        try:
            df = pdr.DataReader(series_id, "fred", start=start, end=end)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            print(f"[WARN] pandas_datareader fetch failed for {series_id}: {e}")

        # Final fallback: direct FRED API HTTP call
        try:
            params = {
                "series_id": series_id,
                "api_key": self.fred_key or "",
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
            }
            resp = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params=params,
                timeout=10,
                headers={"User-Agent": "modular-quant-platform/credit-fetcher"},
            )
            if resp.status_code != 200:
                print(f"[WARN] FRED HTTP fetch failed for {series_id}: HTTP {resp.status_code} {resp.text[:200]}")
                return pd.DataFrame()
            data = resp.json()
            obs = data.get("observations", [])
            if not obs:
                print(f"[WARN] FRED HTTP returned no observations for {series_id}")
                return pd.DataFrame()
            rows = []
            for o in obs:
                try:
                    val = float(o.get("value"))
                except Exception:
                    continue
                rows.append({"Date": pd.to_datetime(o.get("date")), series_id: val})
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows).set_index("Date").sort_index()
            return df
        except Exception as e:
            print(f"[WARN] FRED HTTP fetch failed for {series_id}: {e}")
            return pd.DataFrame()


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

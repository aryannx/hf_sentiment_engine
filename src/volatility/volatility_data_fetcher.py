from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf


@dataclass
class TermStructureMetrics:
    front: float
    second: float
    ratio: float
    slope: float
    contango: bool


class VolatilityDataFetcher:
    """
    Fetch VIX spot, VIX futures curve, and proxy ETFs for long/short volatility.
    Uses yfinance tickers:
      - Spot VIX: ^VIX
      - Futures: VX1!, VX2!, VX3!, VX4! (front to back months)
      - Proxies: UVXY (long vol), SVXY (short vol)
    """

    def __init__(self) -> None:
        pass

    def fetch_vix_spot(self, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        df = yf.download("^VIX", period=period, interval=interval, progress=False)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index().rename(columns={"Date": "Date", "Close": "Close"})
        return df[["Date", "Close"]]

    def fetch_vix_futures_curve(
        self,
        futures: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        tickers = futures or ["VX1!", "VX2!", "VX3!", "VX4!"]
        data = yf.download(" ".join(tickers), period="5d", interval="1d", progress=False)
        if data.empty:
            return pd.DataFrame()
        # yfinance returns columns MultiIndex (Close, ticker)
        closes = data["Close"].iloc[-1]
        curve = pd.DataFrame({"ticker": closes.index, "price": closes.values})
        return curve

    def compute_term_structure(self, curve: pd.DataFrame) -> Optional[TermStructureMetrics]:
        if curve.empty or "price" not in curve.columns:
            return None
        prices = dict(zip(curve["ticker"], curve["price"]))
        front = prices.get("VX1!")
        second = prices.get("VX2!")
        if front is None or second is None or second == 0:
            return None
        ratio = front / second
        slope = (second - front) / front
        contango = front < second
        return TermStructureMetrics(front=front, second=second, ratio=ratio, slope=slope, contango=contango)

    def fetch_proxies(
        self,
        long_vol: str = "UVXY",
        short_vol: str = "SVXY",
        period: str = "1y",
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        tickers = [long_vol, short_vol]
        data = yf.download(" ".join(tickers), period=period, interval=interval, progress=False, group_by="ticker")
        out: Dict[str, pd.DataFrame] = {}
        for t in tickers:
            if t not in data:
                continue
            df = data[t].reset_index()
            df = df.rename(columns={"Close": "Close"})
            out[t] = df[["Date", "Close"]]
        return out


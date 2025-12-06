from __future__ import annotations

from typing import Callable, Optional

import pandas as pd


def estimate_adv_from_bars(bars: pd.DataFrame, window: int = 20) -> float:
    """
    Estimate ADV (average dollar volume) from OHLCV bars with 'Close' and 'Volume'.
    """
    if bars.empty or "Close" not in bars or "Volume" not in bars:
        return 0.0
    dollar_vol = bars["Close"] * bars["Volume"]
    return float(dollar_vol.tail(window).mean())


def estimate_spread_from_quotes(quotes: pd.DataFrame, window: int = 20) -> float:
    """
    Estimate spread in bps from quotes DataFrame with 'bid'/'ask'.
    """
    if quotes.empty or "bid" not in quotes or "ask" not in quotes:
        return 0.0
    mid = (quotes["bid"] + quotes["ask"]) / 2
    spread = (quotes["ask"] - quotes["bid"]) / mid
    return float((spread.tail(window).mean()) * 10_000)


def compute_vwap_from_bars(bars: pd.DataFrame) -> float:
    if bars.empty or "Close" not in bars or "Volume" not in bars:
        return 0.0
    vwap_num = (bars["Close"] * bars["Volume"]).sum()
    vol = bars["Volume"].sum()
    return float(vwap_num / vol) if vol else 0.0


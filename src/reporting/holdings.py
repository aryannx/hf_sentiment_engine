from __future__ import annotations

from typing import Dict, List
import pandas as pd


def holdings_snapshot(positions: Dict[str, float], prices: Dict[str, float]) -> pd.DataFrame:
    rows = []
    for tkr, qty in positions.items():
        px = prices.get(tkr, 0.0)
        mv = qty * px
        rows.append({"ticker": tkr, "qty": qty, "price": px, "market_value": mv})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["weight"] = df["market_value"] / df["market_value"].sum()
    return df.sort_values("market_value", ascending=False)


def top_holdings(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return df
    return df.head(n)[["ticker", "qty", "market_value", "weight"]]


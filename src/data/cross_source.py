from __future__ import annotations

from typing import Dict, Tuple, Optional

import pandas as pd


def compare_prices(primary: Dict[str, float], secondary: Dict[str, float], tolerance_pct: float = 0.01) -> Tuple[bool, Dict[str, float]]:
    """
    Compare primary vs secondary prices; returns (ok, diffs) where diffs are pct differences.
    """
    diffs = {}
    ok = True
    for tkr, p_px in primary.items():
        s_px = secondary.get(tkr)
        if s_px is None or s_px == 0:
            continue
        pct_diff = abs(p_px - s_px) / s_px
        diffs[tkr] = pct_diff
        if pct_diff > tolerance_pct:
            ok = False
    return ok, diffs


def cross_source_price_check(primary_source: str, primary_df: pd.DataFrame, secondary_df: pd.DataFrame, tolerance: float = 0.01) -> Optional[str]:
    if primary_df.empty or secondary_df.empty:
        return "one of the sources has empty data"
    merged = primary_df.merge(secondary_df, left_index=True, right_index=True, how="inner", suffixes=("_p", "_s"))
    if merged.empty:
        return "no overlapping dates between sources"
    merged["diff"] = (merged.iloc[:, 0] - merged.iloc[:, 1]).abs() / merged.iloc[:, 0]
    bad = merged[merged["diff"] > tolerance]
    if not bad.empty:
        return f"{primary_source}: cross-source diff exceeded tolerance {tolerance}: {bad['diff'].max():.4f}"
    return None


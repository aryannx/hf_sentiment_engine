from __future__ import annotations

from typing import Dict, Tuple


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


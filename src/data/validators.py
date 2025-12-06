from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from src.core.notifier import notify


def check_staleness(df: pd.DataFrame, date_col: str = "Date", max_age_days: int = 2) -> List[str]:
    msgs = []
    if df.empty or date_col not in df.columns:
        msgs.append("staleness: missing data or Date column")
        return msgs
    newest = pd.to_datetime(df[date_col]).max()
    if newest < datetime.utcnow() - timedelta(days=max_age_days):
        msgs.append(f"staleness: newest {newest.date()} older than {max_age_days}d")
    return msgs


def check_missing(df: pd.DataFrame, required_cols: List[str]) -> List[str]:
    msgs = []
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        msgs.append(f"schema: missing columns {missing}")
        return msgs
    if df[required_cols].isnull().any().any():
        msgs.append("missing: NaNs detected in required columns")
    return msgs


def check_spikes(df: pd.DataFrame, price_col: str = "Close", z_thresh: float = 5.0) -> List[str]:
    msgs = []
    if price_col not in df.columns or len(df) < 3:
        return msgs
    rets = df[price_col].pct_change().dropna()
    if rets.std() == 0:
        return msgs
    z = (rets - rets.mean()) / rets.std()
    if (z.abs() > z_thresh).any() or rets.abs().max() > 0.2:
        msgs.append(f"anomaly: price spike beyond {z_thresh} sigma or >20% move")
    return msgs


def run_validations(df: pd.DataFrame, required_cols: List[str], date_col: str = "Date") -> List[str]:
    return _run_validations(df, required_cols, date_col=date_col, alert=False, notifier=None)


def _run_validations(
    df: pd.DataFrame,
    required_cols: List[str],
    date_col: str = "Date",
    alert: bool = False,
    notifier: Optional[Callable[[str, str], None]] = None,
) -> List[str]:
    """
    Core validator runner. Set alert=True to emit warnings via notifier/notify.
    """
    msgs: List[str] = []
    msgs.extend(check_staleness(df, date_col=date_col))
    msgs.extend(check_missing(df, required_cols))
    msgs.extend(check_spikes(df))

    if alert and msgs:
        for m in msgs:
            if notifier:
                notifier(m, "warn")
            else:
                notify(m, level="warn")
    return msgs


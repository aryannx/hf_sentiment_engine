from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .volatility_data_fetcher import TermStructureMetrics


@dataclass
class VolSignalConfig:
    backwardation_ratio: float = 1.02  # ratio > 1.02 -> backwardation
    contango_ratio: float = 0.98       # ratio < 0.98 -> strong contango
    vix_long_threshold: float = 30.0
    vix_short_threshold: float = 20.0


class VolatilitySignalGenerator:
    """
    Generate long/short volatility signals from VIX term structure and spot levels.
    Signals:
      +1 long vol when backwardation or high VIX
      -1 short vol when strong contango and low VIX
      0 neutral otherwise
    """

    def __init__(self, config: VolSignalConfig = VolSignalConfig()) -> None:
        self.config = config

    def generate_signal_point(self, metrics: TermStructureMetrics, vix_spot: float) -> int:
        if metrics is None or vix_spot is None:
            return 0
        # Long vol: backwardation or high VIX
        if metrics.ratio > self.config.backwardation_ratio or vix_spot >= self.config.vix_long_threshold:
            return 1
        # Short vol: strong contango and low/moderate VIX
        if metrics.ratio < self.config.contango_ratio and vix_spot <= self.config.vix_short_threshold:
            return -1
        return 0

    def generate_series(
        self,
        term_structure_series: pd.DataFrame,
        vix_series: pd.Series,
    ) -> pd.Series:
        """
        term_structure_series: DataFrame with columns ['ratio'] indexed by date
        vix_series: aligned VIX close series
        """
        signals: List[int] = []
        for date, row in term_structure_series.iterrows():
            ratio = row.get("ratio")
            if pd.isna(ratio):
                signals.append(0)
                continue
            vix_val = vix_series.loc[date] if date in vix_series.index else np.nan
            if pd.isna(vix_val):
                signals.append(0)
                continue
            dummy_metrics = TermStructureMetrics(front=1, second=1, ratio=ratio, slope=0, contango=ratio < 1)
            signals.append(self.generate_signal_point(dummy_metrics, float(vix_val)))
        return pd.Series(signals, index=term_structure_series.index, name="signal")


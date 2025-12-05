# src/credit/credit_signal_generator.py
"""
CreditSignalGenerator: IG vs HY spread-timing signals.

Core idea:
- Trade the relative value between investment grade (IG) and high yield (HY)
  credit using:
    * LQD (IG ETF) and HYG (HY ETF) prices
    * Optional ICE BofA IG/HY OAS spread indices from FRED
    * Daily macro credit sentiment

Signal semantics:
- +1  → Overweight IG / underweight HY (long LQD, short HYG)
- -1  → Overweight HY / underweight IG (long HYG, short LQD)
- 0   → Neutral (flat pair)

Enhancement:
- Optional "extreme OAS percentile" filter so trades only occur when HY OAS
  is at extreme percentiles (e.g., top/bottom 10% of a long history), not
  every time a short-window z-score crosses a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from src.core.base_signal_generator import BaseSignalGenerator


@dataclass
class CreditSignalGenerator(BaseSignalGenerator):
    """
    Signal generator for IG vs HY relative-value trades.

    Expects:
      aligned_df: DataFrame indexed by Date with at least:
          - close_ig, close_hy
          - ret_ig, ret_hy
          - hy_minus_ig_ret      (HY return minus IG return)
      sentiment: pd.Series indexed by Date with macro credit sentiment in [-1, 1]
      oas_df   : optional DataFrame with:
          - ig_oas, hy_oas, hy_ig_oas_spread  (HY OAS − IG OAS)
    """

    def generate_signal(
        self,
        aligned_df: pd.DataFrame,
        sentiment: pd.Series,
        oas_df: Optional[pd.DataFrame] = None,
        sentiment_threshold: float = 0.05,
        z_window: int = 60,
        z_threshold: float = 1.0,
        use_percentile_filter: bool = True,
        lower_percentile: float = 10.0,
        upper_percentile: float = 90.0,
    ) -> np.ndarray:
        """
        Generate daily IG vs HY allocation signals.

        Parameters
        ----------
        aligned_df : DataFrame
            Output of CreditDataFetcher.align_ig_hy (aligned LQD/HYG).
        sentiment : Series
            Daily macro credit sentiment, reindexed to aligned_df.index.
        oas_df : DataFrame, optional
            OAS spread data from FRED with columns:
                'hy_oas', 'ig_oas', 'hy_ig_oas_spread'.
            If None or empty, a price-based spread proxy is used instead.
        sentiment_threshold : float
            |sentiment| above this is considered meaningful risk-on/off.
        z_window : int
            Rolling window (in trading days) for spread z-score.
        z_threshold : float
            |z_spread| above this is considered statistically wide/tight.
        use_percentile_filter : bool
            If True, only allow trades when HY OAS is in extreme percentiles
            (e.g., below 10th or above 90th percentile) based on history.
        lower_percentile : float
            Lower percentile threshold for HY OAS (e.g., 10.0 for 10th percentile).
        upper_percentile : float
            Upper percentile threshold for HY OAS (e.g., 90.0 for 90th percentile).

        Returns
        -------
        np.ndarray[int]
            Array of signals (+1, 0, -1) aligned to aligned_df.index.
        """
        if aligned_df.empty:
            raise ValueError("aligned_df is empty; cannot generate credit signals.")

        df = aligned_df.copy()

        # 1) Align sentiment to the price index
        sent = sentiment.reindex(df.index).fillna(0.0)

        # 2) Choose spread measure: OAS if available, else price-based proxy
        use_oas = (
            oas_df is not None
            and not oas_df.empty
            and "hy_ig_oas_spread" in oas_df.columns
        )

        if use_oas:
            # Align OAS data to trading days
            oas_aligned = oas_df.reindex(df.index).ffill().bfill()

            # Main spread series for z-score
            spread = oas_aligned["hy_ig_oas_spread"].astype(float)

            # HY OAS level for percentile filter
            if "hy_oas" in oas_aligned.columns:
                hy_oas = oas_aligned["hy_oas"].astype(float)
            else:
                # Fallback: if hy_oas is missing, disable percentile filter
                hy_oas = None
                use_percentile_filter = False

        else:
            # No OAS: fall back to price-based cumulative HY-IG spread proxy
            if "hy_minus_ig_ret" not in df.columns:
                raise ValueError(
                    "aligned_df must contain 'hy_minus_ig_ret' when OAS data is not provided."
                )
            spread = df["hy_minus_ig_ret"].cumsum()
            hy_oas = None
            use_percentile_filter = False  # percentile filter needs actual OAS

        # 3) Rolling z-score of chosen spread
        roll_mean = spread.rolling(z_window, min_periods=z_window // 2).mean()
        roll_std = spread.rolling(z_window, min_periods=z_window // 2).std()
        roll_std_safe = roll_std.replace(0.0, np.nan)
        z_spread = ((spread - roll_mean) / roll_std_safe).fillna(0.0)

        # 4) Core conditions (same as before)
        risk_on = sent > sentiment_threshold
        risk_off = sent < -sentiment_threshold
        spreads_wide = z_spread > z_threshold      # HY cheap vs IG
        spreads_tight = z_spread < -z_threshold    # HY rich vs IG

        # 5) Extreme HY OAS percentile filter (optional)
        if use_percentile_filter and hy_oas is not None:
            # Compute percentiles from the historical distribution of HY OAS
            # (using all available history in oas_df)
            hy_oas_hist = hy_oas.dropna().to_numpy()
            if hy_oas_hist.size >= 50:  # need enough history to make this meaningful
                low_cut = np.percentile(hy_oas_hist, lower_percentile)
                high_cut = np.percentile(hy_oas_hist, upper_percentile)

                extreme = (hy_oas <= low_cut) | (hy_oas >= high_cut)
            else:
                # Not enough history: disable filter
                extreme = pd.Series(True, index=df.index)
            # Combine with existing conditions
            spreads_wide = spreads_wide & extreme
            spreads_tight = spreads_tight & extreme
        # else: no percentile filter, keep spreads_wide/tight as-is

        # 6) Map to signals
        signals = np.zeros(len(df), dtype=int)

        # Risk-off + spreads tight  → long IG / short HY
        long_ig = risk_off & spreads_tight

        # Risk-on + spreads wide   → long HY / short IG
        long_hy = risk_on & spreads_wide

        signals[long_ig.to_numpy()] = +1
        signals[long_hy.to_numpy()] = -1

        return signals

    def compute_pair_trade_returns(
        self,
        aligned_df: pd.DataFrame,
        signals: np.ndarray,
        notional: float = 1.0,
    ) -> pd.Series:
        """
        Compute daily strategy returns for the IG/HY pair trade.

        signal = +1 → +notional * ret_ig - notional * ret_hy
        signal = -1 → +notional * ret_hy - notional * ret_ig
        signal =  0 → 0
        """
        df = aligned_df.copy()
        if "ret_ig" not in df.columns or "ret_hy" not in df.columns:
            raise ValueError("aligned_df must contain 'ret_ig' and 'ret_hy'.")
        if len(df) != len(signals):
            raise ValueError("aligned_df and signals must have the same length.")

        ret_ig = df["ret_ig"].to_numpy()
        ret_hy = df["ret_hy"].to_numpy()
        sig = np.asarray(signals, dtype=float)

        long_ig_mask = sig == 1.0
        long_hy_mask = sig == -1.0

        strat_ret = np.zeros_like(sig, dtype=float)
        strat_ret[long_ig_mask] = notional * (ret_ig[long_ig_mask] - ret_hy[long_ig_mask])
        strat_ret[long_hy_mask] = notional * (ret_hy[long_hy_mask] - ret_ig[long_hy_mask])

        return pd.Series(strat_ret, index=df.index, name="credit_pair_return")

"""
Signal generator dedicated to intraday mean reversion / breakout overlays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from src.core.base_signal_generator import BaseSignalGenerator


def _stoch_cross(k: pd.Series, d: pd.Series, direction: str) -> pd.Series:
    prev_diff = k.shift(1) - d.shift(1)
    curr_diff = k - d
    if direction == "up":
        return (prev_diff <= 0) & (curr_diff > 0)
    return (prev_diff >= 0) & (curr_diff < 0)


@dataclass
class IntradaySignalGenerator(BaseSignalGenerator):
    """
    Encodes style-specific parameters for the intraday module.
    """

    STYLE_CONFIG: Dict[str, Dict[str, float]] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.STYLE_CONFIG is None:
            self.STYLE_CONFIG = {
                "rare": {
                    "rsi_low": 16,
                    "rsi_high": 84,
                    "band_distance": 2.5,
                    "delta_neutral": 0.35,
                    "volume_mult": 1.10,
                    "support_tolerance": 0.003,  # 30 bps
                    "use_slow": True,
                    "max_regime_width": 0.09,
                    "ema_slope_limit": 0.2,
                },
                "frequent": {
                    "rsi_low": 20,
                    "rsi_high": 80,
                    "band_distance": 1.2,
                    "delta_neutral": 0.5,
                    "volume_mult": 1.0,
                    "support_tolerance": 0.005,
                    "use_slow": False,
                    "max_regime_width": 0.12,
                    "ema_slope_limit": 0.35,
                },
            }

    def generate_signal(  # type: ignore[override]
        self,
        data: pd.DataFrame,
        sentiment_score: Optional[float] = None,  # unused but kept for interface parity
        *,
        style: str = "rare",
        confirmations: Optional[Iterable[str]] = None,
        delta_series: Optional[pd.Series] = None,
        support_levels: Optional[Iterable[float]] = None,
        allow_breakout: bool = False,
    ) -> np.ndarray:
        setups = self.scan_for_setups(
            data,
            style=style,
            confirmations=confirmations,
            delta_series=delta_series,
            support_levels=support_levels,
            allow_breakout=allow_breakout,
        )
        signals = np.zeros(len(data))
        for idx, row in setups.iterrows():
            signals[idx] = row["direction"]
        if not hasattr(self, "signals"):
            self.signals = {}
        self.signals["intraday"] = setups
        return signals

    def scan_for_setups(
        self,
        data: pd.DataFrame,
        *,
        style: str = "rare",
        confirmations: Optional[Iterable[str]] = None,
        delta_series: Optional[pd.Series] = None,
        support_levels: Optional[Iterable[float]] = None,
        allow_breakout: bool = False,
    ) -> pd.DataFrame:
        cfg = self.STYLE_CONFIG.get(style, self.STYLE_CONFIG["rare"])
        confirmations = tuple(confirmations or [])

        df = data.reset_index(drop=True).copy()
        if delta_series is not None:
            delta_series = delta_series.reindex(df.index).ffill()

        k_col = "SLOW_K" if cfg["use_slow"] else "FAST_K"
        d_col = "SLOW_D" if cfg["use_slow"] else "FAST_D"
        df["CROSS_LONG"] = _stoch_cross(df[k_col], df[d_col], "up")
        df["CROSS_SHORT"] = _stoch_cross(df[k_col], df[d_col], "down")

        signals: List[Dict] = []
        support_arr = np.array(list(support_levels)) if support_levels else None

        for idx in range(2, len(df)):
            row = df.iloc[idx]
            regime = row.get("REGIME", "sideways")

            if regime == "trending" and not allow_breakout:
                continue

            long_trigger = (
                row["RSI"] <= cfg["rsi_low"]
                and row["BAND_DISTANCE"] <= -cfg["band_distance"]
                and bool(row["CROSS_LONG"])
            )
            short_trigger = (
                row["RSI"] >= cfg["rsi_high"]
                and row["BAND_DISTANCE"] >= cfg["band_distance"]
                and bool(row["CROSS_SHORT"])
            )

            if not long_trigger and not short_trigger:
                continue

            direction = 1 if long_trigger else -1
            if not self._regime_allows(row, cfg, allow_breakout, direction):
                continue

            if delta_series is not None:
                if abs(float(delta_series.iloc[idx])) > cfg["delta_neutral"]:
                    continue

            context = self._context_snapshot(df, idx)
            if not self._passes_confirmations(
                row,
                context,
                confirmations,
                support_arr,
                direction,
                cfg,
            ):
                continue

            signals.append(
                {
                    "index": idx,
                    "timestamp": row.get("Date", df.index[idx]),
                    "direction": direction,
                    "regime": regime,
                    "rsi": row["RSI"],
                    "band_distance": row["BAND_DISTANCE"],
                    "volume_z": context["volume_z"],
                    "setup_reason": self._build_reason(direction, confirmations, context),
                }
            )

        if not signals:
            return pd.DataFrame(columns=["direction"])

        setups_df = pd.DataFrame(signals).set_index("index")
        return setups_df

    def _regime_allows(
        self,
        row: pd.Series,
        cfg: Dict[str, float],
        allow_breakout: bool,
        direction: int,
    ) -> bool:
        if allow_breakout and row.get("REGIME") == "trending":
            # Require bands tightening plus slope in trade direction.
            slope = row.get("EMA_SLOPE", 0.0)
            band = row.get("BB_WIDTH_PCT", 0.0)
            if band <= cfg["max_regime_width"]:
                return True
            if direction == 1 and slope < cfg["ema_slope_limit"]:
                return True
            if direction == -1 and slope > -cfg["ema_slope_limit"]:
                return True
            return False

        return row.get("BB_WIDTH_PCT", 0) <= cfg["max_regime_width"]

    def _context_snapshot(self, df: pd.DataFrame, idx: int) -> Dict[str, float]:
        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]
        price = float(row["Close"])
        rsi = float(row["RSI"])
        volume_ma = row.get("VOLUME_MA") or 0.0
        volume_z = 0.0
        if volume_ma:
            volume_z = (row["Volume"] - volume_ma) / volume_ma

        return {
            "price": price,
            "prev_price": float(prev_row["Close"]),
            "rsi": rsi,
            "prev_rsi": float(prev_row["RSI"]),
            "volume_z": volume_z,
            "bb_upper": float(row.get("BB_UPPER", np.nan)),
            "bb_lower": float(row.get("BB_LOWER", np.nan)),
        }

    def _passes_confirmations(
        self,
        row: pd.Series,
        context: Dict[str, float],
        confirmations: Iterable[str],
        support_arr: Optional[np.ndarray],
        direction: int,
        cfg: Dict[str, float],
    ) -> bool:
        for item in confirmations:
            if item == "volume":
                if context["volume_z"] < 0 and direction == 1:
                    return False
                if context["volume_z"] > 0 and direction == -1:
                    pass
            elif item == "divergence":
                price_cond = (
                    direction == 1 and context["price"] <= context["prev_price"]
                ) or (direction == -1 and context["price"] >= context["prev_price"])
                rsi_cond = (
                    direction == 1 and context["rsi"] > context["prev_rsi"]
                ) or (direction == -1 and context["rsi"] < context["prev_rsi"])
                if not (price_cond and rsi_cond):
                    return False
            elif item == "support":
                if support_arr is None:
                    return False
                diff = np.min(np.abs(support_arr - context["price"]))
                if diff > cfg["support_tolerance"] * context["price"]:
                    return False
        return True

    def _build_reason(
        self,
        direction: int,
        confirmations: Iterable[str],
        context: Dict[str, float],
    ) -> str:
        base = "RSI<=16" if direction == 1 else "RSI>=84"
        parts = [base]
        for item in confirmations:
            if item == "volume":
                parts.append("volume_spike" if context["volume_z"] > 0 else "volume_dry")
            elif item == "divergence":
                parts.append("rsi_divergence")
            elif item == "support":
                parts.append("near_support")
        return ",".join(parts)


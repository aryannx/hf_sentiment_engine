"""
Backtesting helper for intraday signal sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .intraday_signal_generator import IntradaySignalGenerator


@dataclass
class IntradayBacktester:
    """
    Lightweight simulator that assumes entries on the close of the signal bar
    and exits when price reverts to the mid Bollinger band or after a max hold.
    """

    initial_cash: float = 100_000.0
    max_hold_bars: int = 12
    cost_bps: float = 2.0
    metric_helper: IntradaySignalGenerator = field(default_factory=IntradaySignalGenerator)

    def run_backtest(
        self,
        price_data: pd.DataFrame,
        *,
        signals: Optional[np.ndarray] = None,
        signal_generator: Optional[IntradaySignalGenerator] = None,
        generator_kwargs: Optional[Dict] = None,
    ) -> Dict[str, object]:
        if signals is None:
            if signal_generator is None:
                signal_generator = IntradaySignalGenerator()
            kwargs = generator_kwargs or {}
            signals = signal_generator.generate_signal(price_data, **kwargs)
            metadata = signal_generator.signals.get("intraday")
        else:
            metadata = None

        trades = self._simulate_trades(price_data, signals, metadata)
        returns = pd.Series([t["return"] for t in trades]) if trades else pd.Series(dtype=float)

        sharpe = self.metric_helper.calculate_sharpe_ratio(returns) if not returns.empty else 0.0
        max_dd = self.metric_helper.calculate_max_drawdown(returns) if not returns.empty else 0.0

        equity_curve = (1.0 + returns.fillna(0.0)).cumprod() * self.initial_cash
        final_value = float(equity_curve.iloc[-1]) if not equity_curve.empty else self.initial_cash

        return {
            "starting_cash": self.initial_cash,
            "final_value": final_value,
            "pnl": final_value - self.initial_cash,
            "total_return": (final_value - self.initial_cash) / self.initial_cash if self.initial_cash else 0.0,
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "trades": trades,
            "trade_count": len(trades),
        }

    def _simulate_trades(
        self,
        price_data: pd.DataFrame,
        signals: np.ndarray,
        metadata: Optional[pd.DataFrame],
    ) -> List[Dict[str, object]]:
        trades: List[Dict[str, object]] = []
        df = price_data.reset_index(drop=True)
        cost = self.cost_bps / 10_000

        for idx, sig in enumerate(signals):
            if sig == 0:
                continue
            entry_price = float(df.loc[idx, "Close"])
            exit_idx = None
            exit_price = None
            for forward in range(1, self.max_hold_bars + 1):
                if idx + forward >= len(df):
                    break
                future = df.loc[idx + forward]
                mid = future.get("BB_MIDDLE", future["Close"])
                if sig == 1 and future["Close"] >= mid:
                    exit_idx = idx + forward
                    exit_price = float(future["Close"])
                    break
                if sig == -1 and future["Close"] <= mid:
                    exit_idx = idx + forward
                    exit_price = float(future["Close"])
                    break
            if exit_idx is None:
                exit_idx = min(idx + self.max_hold_bars, len(df) - 1)
                exit_price = float(df.loc[exit_idx, "Close"])

            pnl = (exit_price - entry_price) * sig
            ret = pnl / entry_price - cost
            trade = {
                "entry_index": idx,
                "exit_index": exit_idx,
                "direction": int(sig),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return": ret,
            }
            if metadata is not None and idx in metadata.index:
                meta_row = metadata.loc[idx]
                trade["setup_reason"] = meta_row.get("setup_reason")
                trade["band_distance"] = meta_row.get("band_distance")
                trade["rsi"] = meta_row.get("rsi")
            trades.append(trade)
        return trades


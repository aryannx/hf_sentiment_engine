from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class VolBacktestConfig:
    initial_cash: float = 100000.0
    cost_bps: float = 5.0
    long_vol_ticker: str = "UVXY"
    short_vol_ticker: str = "SVXY"


class VolatilityBacktester:
    """
    Simple long/short vol backtester using ETF proxies.
    Signal conventions:
      +1 -> long vol instrument (e.g., UVXY)
      -1 -> short vol instrument (e.g., SVXY)
      0  -> flat
    """

    def __init__(self, config: VolBacktestConfig = VolBacktestConfig()) -> None:
        self.config = config

    def run(
        self,
        signals: pd.Series,
        price_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, float]:
        """
        signals: pd.Series indexed by Date, values in {-1,0,1}
        price_data: mapping {ticker: DataFrame with Date, Close}
        """
        cfg = self.config
        if cfg.long_vol_ticker not in price_data or cfg.short_vol_ticker not in price_data:
            raise ValueError("Missing proxy price data for long/short vol tickers")

        # Align price series
        long_df = price_data[cfg.long_vol_ticker][["Date", "Close"]].rename(columns={"Close": "long"})
        short_df = price_data[cfg.short_vol_ticker][["Date", "Close"]].rename(columns={"Close": "short"})
        merged = (
            long_df.merge(short_df, on="Date", how="inner")
            .merge(signals.rename("signal"), left_on="Date", right_index=True, how="inner")
            .sort_values("Date")
            .reset_index(drop=True)
        )
        if merged.empty:
            raise ValueError("No overlapping data between signals and price series")

        merged["long_ret"] = merged["long"].pct_change().fillna(0.0)
        merged["short_ret"] = merged["short"].pct_change().fillna(0.0)

        # Strategy return depending on signal
        merged["strat_ret"] = 0.0
        long_mask = merged["signal"] == 1
        short_mask = merged["signal"] == -1
        merged.loc[long_mask, "strat_ret"] = merged.loc[long_mask, "long_ret"]
        merged.loc[short_mask, "strat_ret"] = -merged.loc[short_mask, "short_ret"]

        # Transaction costs on signal changes
        sig_changes = merged["signal"].diff().abs().fillna(0.0)
        merged.loc[sig_changes > 0, "strat_ret"] -= cfg.cost_bps / 10000.0

        equity_curve = (1 + merged["strat_ret"]).cumprod() * cfg.initial_cash
        final_value = float(equity_curve.iloc[-1])
        pnl = final_value - cfg.initial_cash
        total_return = pnl / cfg.initial_cash
        sharpe = self._sharpe(merged["strat_ret"])
        max_dd = self._max_drawdown(equity_curve / cfg.initial_cash - 1)

        return {
            "final_value": final_value,
            "pnl": pnl,
            "total_return": total_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "trades": int((sig_changes > 0).sum()),
            "period_days": len(merged),
        }

    @staticmethod
    def _sharpe(rets: pd.Series) -> float:
        std = rets.std()
        if std == 0:
            return 0.0
        return float((rets.mean() / std) * np.sqrt(252))

    @staticmethod
    def _max_drawdown(equity: pd.Series) -> float:
        # equity here is total return series (starting at 0)
        cumulative = (1 + equity).cumprod()
        peak = cumulative.cummax()
        dd = (cumulative - peak) / peak
        return float(dd.min())


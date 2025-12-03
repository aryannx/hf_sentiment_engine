# src/core/base_signal_generator.py
"""
Abstract base class for all signal generators
Defines interface + shared utility methods
Works for equities, credit, volatility, or any asset class
"""

from abc import ABC, abstractmethod
import numpy as np
import pandas as pd


class BaseSignalGenerator(ABC):
    """
    Abstract base for signal generation across all asset classes
    Subclasses implement asset-specific generate_signal() logic
    """

    def __init__(self):
        self.signals = {}

    @abstractmethod
    def generate_signal(self, data, sentiment_score, **kwargs):
        """
        Generate trading signals (asset-specific implementation)

        Args:
            data: pd.DataFrame with price/spread data
            sentiment_score: float (-1 to 1)
            **kwargs: asset-specific parameters

        Returns:
            np.array of signals: 1 (BUY), -1 (SELL), 0 (HOLD)
        """
        pass

    # ============ SHARED UTILITY METHODS ============

    def calculate_win_rate(self, signals, prices):
        """
        Calculate % of profitable trades from signals and price series.
        Treat an open position at the end as being closed on the last bar.
        """
        signals = np.asarray(signals, dtype=float)
        prices = np.asarray(prices, dtype=float)

        trades = []
        in_position = False
        entry_price = None

        for i in range(len(signals)):
            sig = signals[i]
            p = prices[i]

            if sig == 1 and not in_position:
                in_position = True
                entry_price = p

            elif sig == -1 and in_position:
                # Normal exit
                exit_price = p
                profit = exit_price - entry_price
                trades.append(1 if profit > 0 else 0)
                in_position = False
                entry_price = None

        # Forced close at end if still long
        if in_position and entry_price is not None:
            exit_price = prices[-1]
            profit = exit_price - entry_price
            trades.append(1 if profit > 0 else 0)

        win_rate = np.mean(trades) if trades else 0.0
        num_trades = len(trades)
        return win_rate, num_trades

    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.0):
        """
        Calculate Sharpe ratio on a 252-day basis.
        Returns 0 if series is too short or variance is ~0.
        """
        r = np.asarray(returns, dtype=float)
        if r.size < 2:
            return 0.0

        excess = r - risk_free_rate / 252.0
        std = excess.std(ddof=1)
        if std < 1e-8:
            return 0.0

        return float(excess.mean() / std * np.sqrt(252))

    def calculate_max_drawdown(self, returns):
        """Calculate maximum drawdown"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def generate_strategy_report(self, data, signals, sentiment_scores):
        """
        Generate performance report using STRATEGY returns (asset_ret * signals),
        not raw buy-and-hold.
        """
        closes = data['Close'].to_numpy()
        asset_ret = data['Close'].pct_change().fillna(0).to_numpy()
        signals_arr = np.asarray(signals, dtype=float)

        n = min(len(asset_ret), len(signals_arr))
        asset_ret = asset_ret[:n]
        signals_arr = signals_arr[:n]

        strat_ret = asset_ret * signals_arr
        if np.allclose(strat_ret, 0.0):
            sharpe = 0.0
            max_dd = 0.0
        else:
            sharpe = self.calculate_sharpe_ratio(pd.Series(strat_ret))
            max_dd = self.calculate_max_drawdown(pd.Series(strat_ret))

        win_rate, num_trades = self.calculate_win_rate(signals_arr, closes[:n])
        sharpe = self.calculate_sharpe_ratio(pd.Series(strat_ret))
        max_dd = self.calculate_max_drawdown(pd.Series(strat_ret))

        report = {
            'total_signals': int(np.sum(np.abs(signals_arr))),
            'buy_signals': int(np.sum(signals_arr == 1)),
            'sell_signals': int(np.sum(signals_arr == -1)),
            'avg_sentiment': float(np.mean(sentiment_scores)),
            'win_rate': float(win_rate),
            'total_trades': int(num_trades),
            'sharpe_ratio': float(sharpe),
            'max_drawdown': float(max_dd),
            'profitable_trades': int(win_rate * num_trades) if num_trades > 0 else 0,
        }
        return report

# src/equities/equity_backtester.py
"""
EquityBacktester: backtest equity signals with optional credit risk overlay.

Uses:
    - EquitySignalGenerator → daily buy/sell/hold signals
    - Optional credit sentiment for position sizing

Features:
    - Trade-level PnL tracking and reporting
    - Daily metrics (Sharpe, Max DD, Win Rate)
"""

from __future__ import annotations

import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

# Ensure src/ is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from equities.equity_signal_generator import EquitySignalGenerator


@dataclass
class EquityBacktester:
    """
    Backtester for equity signals with optional credit risk sizing.

    Parameters
    ----------
    initial_cash : float
        Starting capital for the strategy.
    notional : float
        Position size as fraction of equity (1.0 = 100%).
    """

    initial_cash: float = 100000.0
    notional: float = 1.0

    def __post_init__(self) -> None:
        self.signal_gen = EquitySignalGenerator()

    def run_backtest(
        self,
        ticker: str,
        signals: np.ndarray,
        price_data: pd.DataFrame,
        risk_multiplier: Optional[pd.Series] = None,
        print_trades: bool = True,
        cost_bps: float = 0.0,
        split_ratio: float = 1.0,
        validate_oos: bool = False,
        adv_lookup: Any = 1_000_000.0,
        spread_lookup: Any = None,
        benchmark_df: Optional[pd.DataFrame] = None,
        benchmark_name: str = "SPY",
        crisis_windows: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, float]:
        """
        Backtest a set of signals on price data.

        Parameters
        ----------
        ticker : str
            Ticker symbol (for reporting)
        signals : np.ndarray
            Array of signals (+1, 0, -1) aligned to price_data
        price_data : pd.DataFrame
            DataFrame with 'Date' and 'Close' columns
        risk_multiplier : pd.Series, optional
            Daily position sizing multiplier (e.g., from credit sentiment)
            If None, uses 1.0 (full notional) every day
        print_trades : bool
            If True, print detailed trade-level PnL report

        Returns
        -------
        dict
            Backtest metrics: final_value, pnl, sharpe, max_dd, win_rate, etc.
        """
        if len(signals) != len(price_data):
            raise ValueError(
                f"signals ({len(signals)}) and price_data ({len(price_data)}) "
                "must have same length"
            )

        df = price_data.copy()
        df["signal"] = signals
        df["close"] = df["Close"].astype(float)

        # Compute daily returns
        df["ret"] = df["close"].pct_change()

        # Apply risk multiplier if provided (e.g., credit sentiment scaling)
        if risk_multiplier is not None:
            risk_mult = risk_multiplier.reindex(df.index).fillna(1.0).to_numpy()
        else:
            risk_mult = np.ones(len(df))

        # Strategy returns: signal * return * notional * risk_multiplier
        sig = df["signal"].to_numpy()
        ret = df["ret"].to_numpy()

        strat_ret = sig * ret * self.notional * risk_mult
        strat_ret[0] = 0.0  # first day always 0
        strat_ret = self._apply_transaction_costs(strat_ret, sig, cost_bps)

        df["strat_ret"] = strat_ret
        df["risk_mult"] = risk_mult

        # Equity curve
        equity = (1.0 + strat_ret).cumprod() * self.initial_cash
        df["equity"] = equity

        final_value = float(equity[-1])
        pnl = final_value - self.initial_cash
        total_return = pnl / self.initial_cash if self.initial_cash != 0 else 0.0
        annualized_return = (1 + total_return) ** (252 / max(len(df), 1)) - 1
        volatility = float(np.std(strat_ret) * np.sqrt(252))

        # Metrics
        strat_ret_series = pd.Series(strat_ret)
        sharpe = self.signal_gen.calculate_sharpe_ratio(strat_ret_series)
        max_dd = self.signal_gen.calculate_max_drawdown(strat_ret_series)

        # Win rate (daily)
        win = (strat_ret > 0).sum()
        total_active = (strat_ret != 0).sum()
        win_rate = win / total_active if total_active > 0 else 0.0

        # Trade count
        sig_changes = pd.Series(sig).diff().fillna(0.0) != 0.0
        trade_count = int(sig_changes.sum())

        # Trade-level PnL
        trades = self._compute_trade_level_pnl(df)

        metrics = {
            "ticker": ticker,
            "starting_cash": self.initial_cash,
            "final_value": final_value,
            "pnl": pnl,
            "total_return": total_return,
            "annualized_return": annualized_return,
            "volatility": volatility,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "trades": trade_count,
            "period_days": len(df),
            "trade_list": trades,
            "cost_bps": cost_bps,
        }

        if validate_oos and 0.0 < split_ratio < 1.0:
            train_metrics, oos_metrics = self._split_metrics(
                df, strat_ret, split_ratio
            )
            if train_metrics:
                metrics["training_metrics"] = train_metrics
            if oos_metrics:
                metrics["oos_metrics"] = oos_metrics
            metrics["split_ratio"] = split_ratio
            metrics["validate_oos"] = True

        if print_trades and len(trades) > 0:
            self._print_trade_report(trades, ticker)

        # Benchmark overlay (e.g., SPY)
        if benchmark_df is not None and not benchmark_df.empty and "Close" in benchmark_df.columns:
            bench_df = benchmark_df.copy()
            bench_df["bench_close"] = bench_df["Close"].astype(float)
            merged = df[["Date", "strat_ret"]].merge(
                bench_df[["Date", "bench_close"]], on="Date", how="inner"
            )
            bench_ret = merged["bench_close"].pct_change().fillna(0.0)
            bench_total = float((1 + bench_ret).prod() - 1)
            bench_annualized = float((1 + bench_total) ** (252 / max(len(bench_ret), 1)) - 1)
            bench_vol = float(bench_ret.std() * np.sqrt(252))
            corr = float(pd.Series(merged["strat_ret"]).corr(bench_ret))
            var_bench = bench_ret.var()
            beta = float(pd.Series(merged["strat_ret"]).cov(bench_ret) / var_bench) if var_bench != 0 else 0.0

            metrics.update(
                {
                    "benchmark": benchmark_name,
                    "benchmark_total_return": bench_total,
                    "benchmark_annualized_return": bench_annualized,
                    "benchmark_volatility": bench_vol,
                    "excess_return": total_return - bench_total,
                    "corr_with_benchmark": corr,
                    "beta_to_benchmark": beta,
                }
            )

        # Crisis replay windows
        if crisis_windows:
            crisis_results = []
            df["Date_dt"] = pd.to_datetime(df["Date"])
            for start, end in crisis_windows:
                window_df = df[(df["Date_dt"] >= pd.to_datetime(start)) & (df["Date_dt"] <= pd.to_datetime(end))]
                if window_df.empty:
                    continue
                window_ret = window_df["strat_ret"].fillna(0.0)
                window_total = float((1 + window_ret).prod() - 1)
                window_dd = float(self.signal_gen.calculate_max_drawdown(window_ret))
                crisis_results.append(
                    {
                        "window": f"{start}->{end}",
                        "total_return": window_total,
                        "max_drawdown": window_dd,
                        "days": len(window_df),
                    }
                )
            if crisis_results:
                metrics["crisis_windows"] = crisis_results

        return metrics

    def _apply_transaction_costs(
        self, strategy_returns: np.ndarray, signals: np.ndarray, cost_bps: float
    ) -> np.ndarray:
        """Subtract transaction costs (in basis points) on signal changes."""
        if cost_bps <= 0.0:
            return strategy_returns

        adjusted = strategy_returns.copy()
        signal_changes = (
            pd.Series(signals, dtype=float).diff().abs().fillna(0.0)
        )
        transaction_rate = cost_bps / 10000.0
        adjusted[signal_changes.to_numpy() > 0.0] -= transaction_rate
        return adjusted

    def _split_metrics(
        self, df: pd.DataFrame, strat_ret: np.ndarray, split_ratio: float
    ) -> Tuple[Optional[Dict[str, float]], Optional[Dict[str, float]]]:
        split_idx = int(len(df) * split_ratio)
        if split_idx <= 1 or split_idx >= len(df):
            return None, None

        date_series = (
            pd.to_datetime(df["Date"])
            if "Date" in df.columns
            else pd.to_datetime(df.index)
        )

        train_returns = strat_ret[:split_idx]
        oos_returns = strat_ret[split_idx:]

        train_metrics = self._section_metrics(
            train_returns, date_series.iloc[:split_idx]
        )
        oos_metrics = self._section_metrics(
            oos_returns, date_series.iloc[split_idx:]
        )
        return train_metrics, oos_metrics

    def _section_metrics(
        self, returns: np.ndarray, dates: pd.Series
    ) -> Optional[Dict[str, float]]:
        if returns.size == 0 or dates.empty:
            return None

        ret_series = pd.Series(returns)
        sharpe = self.signal_gen.calculate_sharpe_ratio(ret_series)
        max_dd = self.signal_gen.calculate_max_drawdown(ret_series)
        equity = (1.0 + ret_series.fillna(0.0)).cumprod()
        total_return = float(equity.iloc[-1] - 1.0)

        return {
            "start_date": str(dates.iloc[0]),
            "end_date": str(dates.iloc[-1]),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "total_return": total_return,
        }

    def _compute_trade_level_pnl(self, df: pd.DataFrame) -> List[Dict]:
        """
        Segment strategy into discrete trades and compute PnL per trade.

        A trade starts when signal changes from 0 to ±1 and ends when
        it returns to 0 or flips direction.
        """
        trades = []
        sig = df["signal"].to_numpy()

        # FIXED: Extract dates from 'Date' column if available, else use index
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"]).dt.date.to_numpy()
        else:
            dates = df.index.to_numpy()

        equity = df["equity"].to_numpy()

        in_trade = False
        trade_start_idx = None
        trade_direction = None
        trade_start_equity = None

        for i in range(len(sig)):
            if not in_trade and sig[i] != 0:
                # Trade entry
                in_trade = True
                trade_start_idx = i
                trade_direction = "LONG" if sig[i] == 1 else "SHORT"
                trade_start_equity = equity[i - 1] if i > 0 else self.initial_cash

            elif in_trade and (sig[i] == 0 or sig[i] != sig[i - 1]):
                # Trade exit (signal flat or direction change)
                trade_end_idx = i - 1
                trade_end_equity = equity[trade_end_idx]
                trade_pnl = trade_end_equity - trade_start_equity
                trade_ret = trade_pnl / trade_start_equity if trade_start_equity != 0 else 0.0

                trades.append({
                    "entry_date": dates[trade_start_idx],
                    "exit_date": dates[trade_end_idx],
                    "direction": trade_direction,
                    "entry_equity": trade_start_equity,
                    "exit_equity": trade_end_equity,
                    "pnl": trade_pnl,
                    "return": trade_ret,
                    "duration_days": trade_end_idx - trade_start_idx + 1,
                })

                # Check if new trade starts immediately
                if sig[i] != 0:
                    in_trade = True
                    trade_start_idx = i
                    trade_direction = "LONG" if sig[i] == 1 else "SHORT"
                    trade_start_equity = equity[i - 1]
                else:
                    in_trade = False

        # Close any open trade at end
        if in_trade:
            trade_end_idx = len(sig) - 1
            trade_end_equity = equity[trade_end_idx]
            trade_pnl = trade_end_equity - trade_start_equity
            trade_ret = trade_pnl / trade_start_equity if trade_start_equity != 0 else 0.0

            trades.append({
                "entry_date": dates[trade_start_idx],
                "exit_date": dates[trade_end_idx],
                "direction": trade_direction,
                "entry_equity": trade_start_equity,
                "exit_equity": trade_end_equity,
                "pnl": trade_pnl,
                "return": trade_ret,
                "duration_days": trade_end_idx - trade_start_idx + 1,
            })

        return trades

    def _print_trade_report(self, trades: List[Dict], ticker: str) -> None:
        """Print detailed trade-level report."""
        print("\n" + "=" * 100)
        print(f"TRADE-LEVEL PnL REPORT – {ticker}")
        print("=" * 100)
        print(f"{'#':<4} {'Entry':>12} {'Exit':>12} {'Dir':<6} {'Days':<5} "
              f"{'Entry $':>12} {'Exit $':>12} {'PnL $':>12} {'Return':>10}")
        print("-" * 100)

        for i, t in enumerate(trades, 1):
            # FIXED: Handle both date objects and timestamps
            entry_date = t["entry_date"]
            exit_date = t["exit_date"]

            if isinstance(entry_date, (pd.Timestamp, datetime)):
                entry_str = entry_date.strftime("%Y-%m-%d")
            else:
                entry_str = str(entry_date)

            if isinstance(exit_date, (pd.Timestamp, datetime)):
                exit_str = exit_date.strftime("%Y-%m-%d")
            else:
                exit_str = str(exit_date)

            print(
                f"{i:<4} {entry_str:>12} {exit_str:>12} {t['direction']:<6} {t['duration_days']:<5} "
                f"${t['entry_equity']:>11,.0f} ${t['exit_equity']:>11,.0f} "
                f"${t['pnl']:>11,.0f} {t['return']:>9.2%}"
            )

        print("-" * 100)

        # Summary stats
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t["pnl"] > 0)
        losing_trades = sum(1 for t in trades if t["pnl"] < 0)
        trade_win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        avg_win = np.mean([t["pnl"] for t in trades if t["pnl"] > 0]) if winning_trades > 0 else 0.0
        avg_loss = np.mean([t["pnl"] for t in trades if t["pnl"] < 0]) if losing_trades > 0 else 0.0

        total_pnl = sum(t["pnl"] for t in trades)

        print(f"Total Trades:        {total_trades}")
        print(f"Winning Trades:      {winning_trades} ({trade_win_rate:.1%})")
        print(f"Losing Trades:       {losing_trades}")
        print(f"Avg Win:             ${avg_win:,.0f}")
        print(f"Avg Loss:            ${avg_loss:,.0f}")
        print(f"Total Trade PnL:     ${total_pnl:,.0f}")
        print("=" * 100)

    @staticmethod
    def report(m: Dict[str, float]) -> None:
        """Pretty-print backtest results."""
        print("\n" + "=" * 70)
        print(f"EQUITY BACKTEST REPORT – {m['ticker']}")
        print("=" * 70)
        print(f"Starting Cash:     ${m['starting_cash']:,.0f}")
        print(f"Final Value:       ${m['final_value']:,.0f}")
        print(f"PnL:               ${m['pnl']:,.0f}")
        print(f"Total Return:      {m['total_return']:.2%}")
        print(f"Sharpe (strategy): {m['sharpe']:.2f}")
        print(f"Max Drawdown:      {m['max_drawdown']:.2%}")
        print(f"Win Rate (daily):  {m['win_rate']:.2%}")
        print(f"Trades:            {m['trades']}")
        print(f"Period (days):     {m['period_days']}")
        if m.get("training_metrics"):
            train = m["training_metrics"]
            print(
                f"Train Sharpe/MaxDD/Return: {train['sharpe']:.2f} / "
                f"{train['max_drawdown']:.2%} / {train['total_return']:.2%}"
            )
        if m.get("oos_metrics"):
            oos = m["oos_metrics"]
            print(
                f"OOS Sharpe/MaxDD/Return:   {oos['sharpe']:.2f} / "
                f"{oos['max_drawdown']:.2%} / {oos['total_return']:.2%}"
            )
        print("=" * 70)

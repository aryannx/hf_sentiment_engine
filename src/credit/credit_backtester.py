# src/credit/credit_backtester.py
"""
CreditBacktester: backtest IG vs HY credit spread-timing strategy.

Uses:
    - CreditDataFetcher        → LQD / HYG ETF prices + OAS spreads
    - CreditSentimentAnalyzer  → daily macro credit sentiment [-1, 1]
    - CreditSignalGenerator    → +1/0/-1 IG vs HY allocation signals
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.core.base_signal_generator import BaseSignalGenerator
from src.credit.credit_data_fetcher import CreditDataFetcher
from src.credit.credit_sentiment_analyzer import CreditSentimentAnalyzer
from src.credit.credit_signal_generator import CreditSignalGenerator

# Ensure project root (folder that contains src/) is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# IMPORTANT: absolute imports from core/credit (same style as before)
from core.base_signal_generator import BaseSignalGenerator
from credit.credit_data_fetcher import CreditDataFetcher
from credit.credit_sentiment_analyzer import CreditSentimentAnalyzer
from credit.credit_signal_generator import CreditSignalGenerator


@dataclass
class CreditBacktester:
    """
    Backtester for IG vs HY relative-value strategy.
    """

    initial_cash: float = 100000.0
    notional_per_leg: float = 1.0

    def __post_init__(self) -> None:
        self.metric_helper = CreditSignalGenerator()

    def run_backtest(
        self,
        period: str = "1y",
        ig_ticker: str = "LQD",
        hy_ticker: str = "HYG",
        sentiment_start: Optional[str] = None,
        sentiment_end: Optional[str] = None,
        sentiment_threshold: float = 0.05,
        z_window: int = 60,
        z_threshold: float = 1.0,
        use_percentile_filter: bool = True,
        lower_percentile: float = 10.0,
        upper_percentile: float = 90.0,
    ) -> Dict[str, float]:
        """
        End-to-end credit backtest for IG vs HY pair.
        """
        # 1) Prices
        fetcher = CreditDataFetcher()
        etfs = fetcher.fetch_ig_hy_pair(period=period, interval="1d")
        ig_df = etfs.get(ig_ticker)
        hy_df = etfs.get(hy_ticker)

        if ig_df is None or hy_df is None or ig_df.empty or hy_df.empty:
            raise RuntimeError("Failed to fetch IG/HY ETF data; cannot run credit backtest.")

        aligned = CreditDataFetcher.align_ig_hy(ig_df, hy_df)

        # 2) OAS spreads
        start_oas = aligned.index.min().strftime("%Y-%m-%d")
        end_oas = aligned.index.max().strftime("%Y-%m-%d")
        oas_df = fetcher.fetch_oas_pair(start=start_oas, end=end_oas)

        # 3) Sentiment
        if sentiment_start is None:
            sentiment_start = start_oas
        if sentiment_end is None:
            sentiment_end = end_oas

        sent_analyzer = CreditSentimentAnalyzer()
        daily_sent = sent_analyzer.get_daily_sentiment_series(sentiment_start, sentiment_end)
        daily_sent = daily_sent.reindex(aligned.index).fillna(0.0)

        # 4) Signals
        sig_gen = CreditSignalGenerator()
        signals = sig_gen.generate_signal(
            aligned_df=aligned,
            sentiment=daily_sent,
            oas_df=oas_df,
            sentiment_threshold=sentiment_threshold,
            z_window=z_window,
            z_threshold=z_threshold,
            use_percentile_filter=use_percentile_filter,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
        )

        # 5) Strategy returns
        strat_ret = sig_gen.compute_pair_trade_returns(
            aligned_df=aligned,
            signals=signals,
            notional=self.notional_per_leg,
        )

        # 6) Metrics
        sharpe = self.metric_helper.calculate_sharpe_ratio(strat_ret)
        max_dd = self.metric_helper.calculate_max_drawdown(strat_ret)

        equity_curve = self._equity_from_returns(strat_ret, self.initial_cash)
        final_value = float(equity_curve.iloc[-1])
        pnl = final_value - self.initial_cash
        total_return = pnl / self.initial_cash if self.initial_cash != 0 else 0.0

        sig_series = pd.Series(signals, index=aligned.index)
        sig_changes = sig_series.diff().fillna(0.0) != 0.0
        trade_count = int(sig_changes.sum())

        return {
            "starting_cash": self.initial_cash,
            "final_value": final_value,
            "pnl": pnl,
            "total_return": total_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "trades": trade_count,
            "period_days": len(aligned),
            "ig_ticker": ig_ticker,
            "hy_ticker": hy_ticker,
            "sentiment_threshold": sentiment_threshold,
            "z_window": z_window,
            "z_threshold": z_threshold,
            "use_percentile_filter": use_percentile_filter,
            "lower_percentile": lower_percentile,
            "upper_percentile": upper_percentile,
        }

    @staticmethod
    def _equity_from_returns(returns: pd.Series, initial_cash: float) -> pd.Series:
        eq = (1.0 + returns.fillna(0.0)).cumprod() * initial_cash
        eq.name = "equity"
        return eq

    def report(self, m: Dict[str, float]) -> None:
        print("\n" + "=" * 70)
        print("CREDIT PAIR BACKTEST REPORT (IG vs HY)")
        print("=" * 70)
        print(f"IG Ticker:         {m['ig_ticker']}")
        print(f"HY Ticker:         {m['hy_ticker']}")
        print("-" * 70)
        print(f"Starting Cash:     ${m['starting_cash']:,.0f}")
        print(f"Final Value:       ${m['final_value']:,.0f}")
        print(f"PnL:               ${m['pnl']:,.0f}")
        print(f"Total Return:      {m['total_return']:.2%}")
        print(f"Sharpe (strategy): {m['sharpe']:.2f}")
        print(f"Max Drawdown:      {m['max_drawdown']:.2%}")
        print(f"Trades (regimes):  {m['trades']}")
        print(f"Period (days):     {m['period_days']}")
        print("-" * 70)
        print(f"sent_thr/z_win/z:  {m['sentiment_threshold']}/{m['z_window']}/{m['z_threshold']}")
        print(f"Percentile Filter: {m['use_percentile_filter']} "
              f"(p{m['lower_percentile']:.0f}–p{m['upper_percentile']:.0f})")
        print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test IG vs HY credit backtester")
    parser.add_argument("--period", default="1y", help="History period (yfinance style)")
    parser.add_argument("--sent_thr", type=float, default=0.05)
    parser.add_argument("--z_window", type=int, default=60)
    parser.add_argument("--z_thr", type=float, default=1.0)
    parser.add_argument("--use_percentile", action="store_true")
    parser.add_argument("--lower_pct", type=float, default=10.0)
    parser.add_argument("--upper_pct", type=float, default=90.0)
    args = parser.parse_args()

    bt = CreditBacktester(initial_cash=100000.0, notional_per_leg=1.0)

    print(
        f"📈 Running credit pair backtest "
        f"(LQD vs HYG, period={args.period}, "
        f"sent_thr={args.sent_thr}, z_win={args.z_window}, z={args.z_thr}, "
        f"percentile={args.use_percentile})..."
    )
    metrics = bt.run_backtest(
        period=args.period,
        sentiment_threshold=args.sent_thr,
        z_window=args.z_window,
        z_threshold=args.z_thr,
        use_percentile_filter=args.use_percentile,
        lower_percentile=args.lower_pct,
        upper_percentile=args.upper_pct,
    )
    bt.report(metrics)
    print("\n✅ Credit backtest complete!")

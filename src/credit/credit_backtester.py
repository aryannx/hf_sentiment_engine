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
import os
import time

from src.core.base_signal_generator import BaseSignalGenerator
from src.credit.credit_data_fetcher import CreditDataFetcher
from src.credit.credit_sentiment_analyzer import CreditSentimentAnalyzer
from src.credit.credit_signal_generator import CreditSignalGenerator
from src.core.compliance_engine import ComplianceEngine
from src.core.compliance_rules import default_compliance_config
from src.core.oms_models import Order, OrderSide
from src.core.oms_simulator import ExecutionSimulator
from src.core.oms_config import ExecutionConfig
from exec.providers.polygon_hooks import adv_lookup_polygon, spread_lookup_polygon
from exec.providers.finnhub_hooks import adv_lookup_finnhub, spread_lookup_finnhub
from src.core.position_ledger import PositionLedger
from risk.config import default_risk_config
from risk.engine import RiskEngine
from risk.models import Position as RiskPosition
from src.core.metrics import MetricsCollector


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
        use_oas_cache: bool = True,
        cache_path: Optional[str] = None,
        ig_oas_series_id: str = "BAMLC0A0CM",
        hy_oas_series_id: str = "BAMLH0A0HYM2",
        simulate_execution: bool = False,
        adv_provider: str = "static",
        spread_provider: str = "static",
    ) -> Dict[str, float]:
        """
        End-to-end credit backtest for IG vs HY pair.
        """
        metrics_collector = MetricsCollector(enable=os.getenv("METRICS_ENABLED") == "1")
        metrics_collector.counter("credit_backtest_start", ig=ig_ticker, hy=hy_ticker)
        start_time = time.time()
        risk_engine = RiskEngine(default_risk_config())
        # 0) Pre-trade compliance (two-leg notional assumption)
        engine = ComplianceEngine(default_compliance_config())
        per_leg = self.notional_per_leg * 100000.0  # interpret notional_per_leg as scaling of base
        pretrade = engine.evaluate_orders(
            orders=[
                {"ticker": ig_ticker, "notional": per_leg},
                {"ticker": hy_ticker, "notional": per_leg},
            ],
            portfolio_value=self.initial_cash,
        )
        if pretrade["decision"] == "block":
            raise RuntimeError(
                "Compliance block before credit backtest: "
                + "; ".join([r.message for r in pretrade["results"] if not r.passed])
            )

        # 1) Prices
        fetcher = CreditDataFetcher(
            cache_path=cache_path,
            ig_oas_series_id=ig_oas_series_id,
            hy_oas_series_id=hy_oas_series_id,
        )
        etfs = fetcher.fetch_ig_hy_pair(period=period, interval="1d")
        ig_df = etfs.get(ig_ticker)
        hy_df = etfs.get(hy_ticker)

        if ig_df is None or hy_df is None or ig_df.empty or hy_df.empty:
            raise RuntimeError("Failed to fetch IG/HY ETF data; cannot run credit backtest.")

        aligned = CreditDataFetcher.align_ig_hy(ig_df, hy_df)

        # Risk limits check on pair notionals
        latest_ig = float(aligned[ig_ticker]["close"].iloc[-1])
        latest_hy = float(aligned[hy_ticker]["close"].iloc[-1])
        positions = [
            RiskPosition(ticker=ig_ticker, qty=1.0, price=latest_ig, sector="IG", beta=1.0),
            RiskPosition(ticker=hy_ticker, qty=-1.0, price=latest_hy, sector="HY", beta=1.0),
        ]
        risk = risk_engine.check_limits(positions, nav=self.initial_cash, strategy="credit", portfolio="default")
        if risk["decision"] == "block":
            raise RuntimeError("Risk block before credit backtest: " + "; ".join([b.message for b in risk["breaches"] if b.severity == "block"]))
        if risk["decision"] == "warn":
            for b in risk["breaches"]:
                if b.severity == "warn":
                    print(f"⚠️ Risk warning: {b.level}:{b.name} -> {b.message}")

        # 2) OAS spreads
        start_oas = aligned.index.min().strftime("%Y-%m-%d")
        end_oas = aligned.index.max().strftime("%Y-%m-%d")
        oas_df = fetcher.fetch_oas_pair(start=start_oas, end=end_oas, use_cache=use_oas_cache)

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

        if simulate_execution:
            orders: list[Order] = []
            last_sig = 0
            for dt, sig in zip(aligned.index, signals):
                if sig != last_sig:
                    side = OrderSide.BUY if sig > 0 else OrderSide.SELL
                    px = aligned.loc[dt, "close_hy"]  # use HY leg as proxy
                    orders.append(
                        Order(
                            order_id=f"{dt.strftime('%Y%m%d')}",
                            ticker=hy_ticker if sig < 0 else ig_ticker,
                            side=side,
                            qty=1.0,
                            px=px,
                        )
                    )
                    last_sig = sig

        def _resolve_lookup(provider: str, poly_fn, finn_fn, default):
            if provider == "polygon":
                return poly_fn
            if provider == "finnhub":
                return finn_fn
            return default

        adv_lookup = _resolve_lookup(adv_provider, adv_lookup_polygon, adv_lookup_finnhub, 1_000_000.0)
        spread_lookup = _resolve_lookup(spread_provider, spread_lookup_polygon, spread_lookup_finnhub, None)

        exec_sim = ExecutionSimulator(
            ExecutionConfig(slippage_bps=cost_bps),
            adv_lookup=adv_lookup,
            spread_lookup=spread_lookup,
        )
            ledger = PositionLedger(starting_cash=self.initial_cash)
            for o in orders:
                o, fills = exec_sim.execute(o)
                ledger.apply_fills(fills)
            marks = {
                ig_ticker: aligned["close_ig"].iloc[-1],
                hy_ticker: aligned["close_hy"].iloc[-1],
            }
            eq_snap = ledger.snapshot(marks)
            final_value = eq_snap["equity"]
            pnl = final_value - self.initial_cash
            total_return = pnl / self.initial_cash if self.initial_cash else 0.0
            sharpe = 0.0
            max_dd = 0.0
            trade_count = len(orders)
        else:
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

        metrics = {
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

        # 7) Post-trade compliance scaffold
        posttrade = engine.post_trade_check(
            positions=[
                {"ticker": ig_ticker, "notional": final_value / 2},
                {"ticker": hy_ticker, "notional": final_value / 2},
            ],
            portfolio_value=final_value,
        )
        if posttrade["decision"] == "block":
            print("❌ Post-trade compliance block recorded (no execution taken):")
            for res in posttrade["results"]:
                if not res.passed and res.severity == "block":
                    print(f"   - {res.name}: {res.message}")
        elif any(r.severity == "warn" for r in posttrade["results"]):
            print("⚠️ Post-trade compliance warnings recorded:")
            for res in posttrade["results"]:
                if res.severity == "warn":
                    print(f"   - {res.name}: {res.message}")

        metrics_collector.timer(
            "credit_backtest_runtime_s", time.time() - start_time, ig=ig_ticker, hy=hy_ticker
        )
        metrics_collector.counter("credit_backtest_end", ig=ig_ticker, hy=hy_ticker)
        return metrics

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
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Return OK and exit for monitoring probes.",
    )
    parser.add_argument("--period", default="1y", help="History period (yfinance style)")
    parser.add_argument("--sent_thr", type=float, default=0.05)
    parser.add_argument("--z_window", type=int, default=60)
    parser.add_argument("--z_thr", type=float, default=1.0)
    parser.add_argument("--use_percentile", action="store_true")
    parser.add_argument("--lower_pct", type=float, default=10.0)
    parser.add_argument("--upper_pct", type=float, default=90.0)
    parser.add_argument(
        "--cache_path",
        default="data/raw/fred_oas.pkl",
        help="Path to cache OAS data (pickle).",
    )
    parser.add_argument(
        "--no_cache",
        action="store_true",
        help="Disable OAS caching (fetch fresh from FRED).",
    )
    parser.add_argument(
        "--ig_oas_series",
        default="BAMLC0A0CM",
        help="FRED series ID for IG OAS (default BAMLC0A0CM).",
    )
    parser.add_argument(
        "--hy_oas_series",
        default="BAMLH0A0HYM2",
        help="FRED series ID for HY OAS (default BAMLH0A0HYM2).",
    )
    parser.add_argument(
        "--adv_provider",
        choices=["static", "polygon", "finnhub"],
        default="static",
        help="ADV source for execution simulation.",
    )
    parser.add_argument(
        "--spread_provider",
        choices=["static", "polygon", "finnhub"],
        default="static",
        help="Spread source for execution simulation.",
    )
    args = parser.parse_args()

    if args.healthcheck:
        print("OK")
        raise SystemExit(0)

    bt = CreditBacktester(initial_cash=100000.0, notional_per_leg=1.0)

    print(
        f"📈 Running credit pair backtest "
        f"(LQD vs HYG, period={args.period}, "
        f"sent_thr={args.sent_thr}, z_win={args.z_window}, z={args.z_thr}, "
        f"percentile={args.use_percentile}, cache={'off' if args.no_cache else args.cache_path}, "
        f"IG_OAS={args.ig_oas_series}, HY_OAS={args.hy_oas_series})..."
    )
    metrics = bt.run_backtest(
        period=args.period,
        sentiment_threshold=args.sent_thr,
        z_window=args.z_window,
        z_threshold=args.z_thr,
        use_percentile_filter=args.use_percentile,
        lower_percentile=args.lower_pct,
        upper_percentile=args.upper_pct,
        use_oas_cache=not args.no_cache,
        cache_path=args.cache_path,
        ig_oas_series_id=args.ig_oas_series,
        hy_oas_series_id=args.hy_oas_series,
        adv_provider=args.adv_provider,
        spread_provider=args.spread_provider,
    )
    bt.report(metrics)
    print("\n✅ Credit backtest complete!")

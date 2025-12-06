# src/main.py
"""
End-to-end runner (equity pipeline, optionally with credit risk overlay):
1) Fetch prices
2) Build daily sentiment from news APIs
3) Generate signals
4) (Optional) Fetch credit sentiment for position sizing
5) Backtest
6) Print report
"""

from datetime import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Add src/ to path for equities imports
sys.path.insert(0, str(Path(__file__).parent))

from equities.equity_data_fetcher import EquityDataFetcher
from equities.equity_sentiment_analyzer import EquitySentimentAnalyzer
from equities.equity_signal_generator import EquitySignalGenerator
from equities.equity_backtester import EquityBacktester
from core.compliance_engine import ComplianceEngine
from core.compliance_rules import default_compliance_config
from core.oms_models import Order, OrderSide
from core.oms_simulator import ExecutionSimulator
from core.oms_config import ExecutionConfig
from core.oms_bridges import AlpacaPaperBridge, FixBridgeStub
from core.position_ledger import PositionLedger
from pms.config import demo_pms_config
from pms.rebalancer import Rebalancer
from core.metrics import MetricsCollector
from risk.config import default_risk_config
from risk.engine import RiskEngine
from risk.models import Position
from exec.providers.polygon_hooks import adv_lookup_polygon, spread_lookup_polygon
from exec.providers.finnhub_hooks import adv_lookup_finnhub, spread_lookup_finnhub

try:
    from credit.credit_sentiment_analyzer import CreditSentimentAnalyzer
    CREDIT_AVAILABLE = True
except ImportError:
    CREDIT_AVAILABLE = False


def _load_watchlist_file(path: Path) -> List[str]:
    if not path.exists():
        print(f"⚠️ Watchlist file not found: {path}")
        return []

    tickers: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        tickers.append(entry.upper())
    return tickers


def _flatten_metrics(metrics: Dict) -> Dict:
    ignore_keys = {"trade_list", "strategy_report"}
    row = {
        k: v
        for k, v in metrics.items()
        if k not in ignore_keys and not isinstance(v, dict)
    }
    for section in ("training_metrics", "oos_metrics"):
        section_data = metrics.get(section)
        if not section_data:
            continue
        for key, value in section_data.items():
            row[f"{section}_{key}"] = value
    return row


def _json_default(value):
    if isinstance(value, (np.integer, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float64)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return str(value)


def _export_watchlist_results(results: List[Dict], output_dir: Path) -> None:
    if not results:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    flattened = [_flatten_metrics(r) for r in results]
    df = pd.DataFrame(flattened)
    csv_path = output_dir / f"equity_watchlist_{timestamp}.csv"
    json_path = output_dir / f"equity_watchlist_{timestamp}.json"
    df.to_csv(csv_path, index=False)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=_json_default)
    print(f"📁 Saved aggregated results → {csv_path.name}, {json_path.name}")


def run_equity_pipeline(
    ticker: str = "AAPL",
    period: str = "1y",
    use_credit_overlay: bool = False,
    mode: str = "position",
    cost_bps: float = 0.0,
    split_ratio: float = 1.0,
    validate_oos: bool = False,
    simulate_execution: bool = False,
    pms_rebalance: bool = False,
    adv_provider: str = "static",
    spread_provider: str = "static",
    benchmark: str = "SPY",
    crisis_windows: Optional[List[str]] = None,
):
    """
    End-to-end equity sentiment + signal + backtest pipeline.

    Parameters
    ----------
    ticker : str
        Equity ticker to backtest
    period : str
        yfinance period string (e.g., "1y", "5y")
    use_credit_overlay : bool
        If True and available, scale equity position size by credit sentiment
    mode : str
        "event"  -> one-bar trades (signals only on entry/exit)
        "position" -> hold position until explicit exit
    """
    metrics_collector = MetricsCollector(enable=os.getenv("METRICS_ENABLED") == "1")
    risk_engine = RiskEngine(default_risk_config())
    metrics_collector.counter("equity_pipeline_start", ticker=ticker, mode=mode)
    start_time = time.time()

    print("=" * 80)
    print(f"SENTIMENT SIGNAL ENGINE – EQUITY PIPELINE [{ticker}] (mode={mode})")
    print("=" * 80)

    # 0) Pre-trade compliance (basic single-name sizing assumption)
    compliance_engine = ComplianceEngine(default_compliance_config())
    proposed_notional = 100000.0  # align with backtester initial cash
    pretrade = compliance_engine.evaluate_orders(
        orders=[{"ticker": ticker, "notional": proposed_notional}],
        portfolio_value=proposed_notional,
    )
    if pretrade["decision"] == "block":
        print("❌ Compliance block:")
        for res in pretrade["results"]:
            if not res.passed and res.severity == "block":
                print(f"   - {res.name}: {res.message}")
        return None
    elif any(r.severity == "warn" for r in pretrade["results"]):
        print("⚠️ Compliance warnings:")
        for res in pretrade["results"]:
            if res.severity == "warn":
                print(f"   - {res.name}: {res.message}")

    # 1) Fetch price data  --------------------
    fetcher = EquityDataFetcher()
    print(f"\n📊 Fetching {ticker} price data ({period})...")
    price_data = fetcher.fetch_stock_data(ticker, period=period)

    if price_data.empty:
        print("❌ No price data")
        return None
    # Fetch benchmark for overlays
    benchmark_df = fetcher.fetch_stock_data(benchmark, period=period)


    print(f"✅ {len(price_data)} rows of OHLCV + indicators")

    # Risk limits check using latest close
    price_hint = float(price_data["Close"].iloc[-1])
    positions = [Position(ticker=ticker, qty=1.0, price=price_hint, sector=None, beta=1.0)]
    risk = risk_engine.check_limits(positions, nav=100000.0, strategy="equity", portfolio="default")
    if risk["decision"] == "block":
        print("❌ Risk block before running pipeline:")
        for b in risk["breaches"]:
            if b.severity == "block":
                print(f" - {b.level}:{b.name} -> {b.message}")
        return None
    if risk["decision"] == "warn":
        for b in risk["breaches"]:
            if b.severity == "warn":
                print(f"⚠️ Risk warning: {b.level}:{b.name} -> {b.message}")

    # 2) Build daily sentiment series from APIs  --------------------
    analyzer = EquitySentimentAnalyzer()
    start = price_data["Date"].min().strftime("%Y-%m-%d")
    end = price_data["Date"].max().strftime("%Y-%m-%d")

    print(f"\n💭 Fetching blended sentiment [{start} → {end}]...")
    daily_sent = analyzer.get_daily_sentiment_series(ticker, start, end)

    if daily_sent.empty:
        print("⚠️ No news found; defaulting to 0 sentiment")
        sentiment_series = np.zeros(len(price_data))
    else:
        # align to trading days
        sentiment_series = (
            daily_sent.reindex(price_data["Date"])
            .fillna(0.0)
            .to_numpy()
        )

    print(f"✅ Built sentiment series. Mean={sentiment_series.mean():.3f}")

    # 3) Generate signals  --------------------
    print("\n🎯 Generating signals...")
    sig_gen = EquitySignalGenerator()
    signals = sig_gen.generate_signal(
        price_data,
        sentiment_series,
        mode=mode,   # "event" or "position"
    )

    buys = int((signals == 1).sum())
    sells = int((signals == -1).sum())
    print(f"✅ Signals: {buys} BUY, {sells} SELL, {int((signals == 0).sum())} HOLD")

    # 4) Optional: Fetch credit sentiment for risk overlay  --------
    risk_multiplier = None
    if use_credit_overlay and CREDIT_AVAILABLE:
        print("\n💳 Fetching credit risk overlay...")
        try:
            credit_analyzer = CreditSentimentAnalyzer()
            credit_sent = credit_analyzer.get_daily_sentiment_series(start, end)
            credit_sent = credit_sent.reindex(price_data["Date"]).fillna(0.0)

            # Convert sentiment to position sizing: -1 → 0.5x, 0 → 1.0x, +1 → 1.5x
            risk_multiplier = 1.0 + 0.5 * credit_sent
            risk_multiplier.index = price_data.index  # align to price_data index

            print(
                f"✅ Credit overlay applied. "
                f"Multiplier range: {risk_multiplier.min():.2f}–{risk_multiplier.max():.2f}"
            )
        except Exception as e:
            print(f"⚠️ Credit overlay failed: {e}. Proceeding without overlay.")
            risk_multiplier = None

    # Choose ADV/spread lookups for execution sim path
    def _resolve_lookup(provider: str, polygon_fn, finnhub_fn, default):
        if provider == "polygon":
            return polygon_fn
        if provider == "finnhub":
            return finnhub_fn
        return default

    # 5) Backtest  --------------------
    print("\n📈 Running backtest...")
    if simulate_execution:
        # Convert signals to orders (simple: trade on signal changes)
        orders = []
        last_sig = 0
        for idx, sig in enumerate(signals):
            if sig != last_sig:
                side = OrderSide.BUY if sig > 0 else OrderSide.SELL
                px = price_data.loc[idx, "Close"]
                orders.append(
                    Order(
                        order_id=f"{ticker}-{idx}",
                        ticker=ticker,
                        side=side,
                        qty=1.0,  # unit size; sizing would be extended later
                        px=px,
                    )
                )
                last_sig = sig

        adv_lookup = _resolve_lookup(adv_provider, adv_lookup_polygon, adv_lookup_finnhub, 1_000_000.0)
        spread_lookup = _resolve_lookup(spread_provider, spread_lookup_polygon, spread_lookup_finnhub, None)

        exec_sim = ExecutionSimulator(
            ExecutionConfig(slippage_bps=cost_bps),
            adv_lookup=adv_lookup,
            spread_lookup=spread_lookup,
        )
        ledger = PositionLedger(starting_cash=100000.0)

        for o in orders:
            o, fills = exec_sim.execute(o)
            ledger.apply_fills(fills)

        marks = {ticker: price_data["Close"].iloc[-1]}
        eq_snap = ledger.snapshot(marks)
        metrics = {
            "starting_cash": 100000.0,
            "final_value": eq_snap["equity"],
            "pnl": eq_snap["equity"] - 100000.0,
            "total_return": (eq_snap["equity"] - 100000.0) / 100000.0,
            "sharpe": 0.0,  # not computed in this simple path
            "max_drawdown": 0.0,
            "trades": len(orders),
            "period_days": len(price_data),
            "cost_bps": cost_bps,
            "mode": mode,
            "validate_oos": validate_oos,
            "strategy_report": {},
        }
    else:
        backtester = EquityBacktester(initial_cash=100000)
        metrics = backtester.run_backtest(
            ticker,
            signals,
            price_data,
            risk_multiplier=risk_multiplier,
            cost_bps=cost_bps,
            split_ratio=split_ratio,
            validate_oos=validate_oos,
            benchmark_df=benchmark_df if not benchmark_df.empty else None,
            benchmark_name=benchmark,
            crisis_windows=[tuple(w.split(":")) for w in crisis_windows] if crisis_windows else None,
        )

    # Optional PMS rebalance proposal (demo config, single-account)
    if pms_rebalance:
        prices = {ticker: price_data["Close"].iloc[-1]}
        cfg = demo_pms_config()
        rebalancer = Rebalancer()
        proposal = rebalancer.compute_rebalance(cfg.portfolios[0], prices)
        print("\n📑 PMS Rebalance Proposal")
        print(f"Portfolio: {proposal.portfolio}, turnover={proposal.turnover:.2%}")
        for o in proposal.orders:
            print(f"  {o.side} {o.qty:.2f} {o.ticker} @ {o.px:.2f} (acct={o.account})")

        # Optionally route through OMS simulator to mimic execution
        if simulate_execution and proposal.orders:
            exec_sim = ExecutionSimulator(ExecutionConfig(route_venues=True))
            fills = rebalancer.execute_orders(proposal.orders, exec_sim)
            print(f"  OMS fills: {len(fills)} (logged to OMS audits)")

    # 5b) Post-trade compliance scaffold (current portfolio notionally at final value)
    posttrade = compliance_engine.post_trade_check(
        positions=[{"ticker": ticker, "notional": metrics.get("final_value", 0.0)}],
        portfolio_value=metrics.get("final_value", 0.0),
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

    # 6) Strategy-level metrics from base class  --------------------
    print("\n📊 Computing strategy metrics (BaseSignalGenerator)...")
    report = sig_gen.generate_strategy_report(price_data, signals, sentiment_series)

    print("\n" + "=" * 80)
    print(f"RESULTS – {ticker}")
    print("=" * 80)
    print(f"Total Signals:      {report['total_signals']}")
    print(f"Buy Signals:        {report['buy_signals']}")
    print(f"Sell Signals:       {report['sell_signals']}")
    print(f"Avg Sentiment:      {report['avg_sentiment']:.3f}")
    print(f"Win Rate:           {report['win_rate']:.2%}")
    print(f"Total Trades:       {report['total_trades']}")
    print(f"Sharpe Ratio:       {report['sharpe_ratio']:.2f}")
    print(f"Max Drawdown:       {report['max_drawdown']:.2%}")
    if use_credit_overlay:
        print(f"Credit Overlay:     YES (position sizing by credit risk)")
    print("=" * 80)
    print(f"Backtester Final Value: ${metrics['final_value']:,.0f}")
    print(f"Backtester Sharpe:     {metrics['sharpe']:.2f}")
    print(f"Backtester Max DD:     {metrics['max_drawdown']:.2%}")
    print("=" * 80)

    metrics_collector.timer(
        "equity_pipeline_runtime_s", time.time() - start_time, ticker=ticker, mode=mode
    )
    metrics_collector.counter("equity_pipeline_end", ticker=ticker, mode=mode)

    metrics["strategy_report"] = report
    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Return OK and exit for monitoring probes.",
    )
    parser.add_argument("--ticker", default="SNAP", help="Equity ticker symbol")
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Space-separated list of tickers to run (overrides --ticker)",
    )
    parser.add_argument(
        "--watchlist_file",
        help="Path to newline-separated watchlist (one ticker per line)",
    )
    parser.add_argument("--period", default="1y", help="History period (yfinance style)")
    parser.add_argument(
        "--credit_overlay",
        action="store_true",
        help="Use credit sentiment for position sizing (if available)",
    )
    parser.add_argument(
        "--mode",
        choices=["event", "position"],
        default="position",
        help="Signal mode: 'event' = one-bar trades, 'position' = hold until exit",
    )
    parser.add_argument(
        "--cost_bps",
        type=float,
        default=0.0,
        help="Per-trade transaction cost in basis points.",
    )
    parser.add_argument(
        "--split",
        type=float,
        default=1.0,
        help="Train/OOS split ratio (0-1). Values <1 enable splitting.",
    )
    parser.add_argument(
        "--validate_oos",
        action="store_true",
        help="Compute train vs OOS metrics using --split ratio.",
    )
    parser.add_argument(
        "--output_dir",
        default="reports",
        help="Directory where aggregated CSV/JSON outputs will be stored.",
    )
    parser.add_argument(
        "--adv_provider",
        choices=["static", "polygon", "finnhub"],
        default="static",
        help="ADV source for execution simulation (simulate_execution mode).",
    )
    parser.add_argument(
        "--spread_provider",
        choices=["static", "polygon", "finnhub"],
        default="static",
        help="Spread source for execution simulation (simulate_execution mode).",
    )
    parser.add_argument(
        "--benchmark",
        default="SPY",
        help="Benchmark ticker for overlay metrics (default: SPY).",
    )
    parser.add_argument(
        "--crisis",
        nargs="*",
        default=["2008-09-01:2009-06-30", "2020-02-15:2020-04-30"],
        help="Crisis windows start:end (YYYY-MM-DD:YYYY-MM-DD). Default GFC & COVID.",
    )
    args = parser.parse_args()

    if args.healthcheck:
        print("OK")
        sys.exit(0)

    requested_tickers: List[str] = []
    if args.tickers:
        requested_tickers.extend(t.upper() for t in args.tickers)
    if args.watchlist_file:
        requested_tickers.extend(
            _load_watchlist_file(Path(args.watchlist_file))
        )
    if not requested_tickers:
        requested_tickers = [args.ticker.upper()]

    # Deduplicate while preserving order
    seen = set()
    tickers = []
    for symbol in requested_tickers:
        if symbol not in seen:
            tickers.append(symbol)
            seen.add(symbol)

    all_metrics = []
    for symbol in tickers:
        try:
            metrics = run_equity_pipeline(
                symbol,
                period=args.period,
                use_credit_overlay=args.credit_overlay,
                mode=args.mode,
                cost_bps=args.cost_bps,
                split_ratio=args.split,
                validate_oos=args.validate_oos,
                adv_provider=args.adv_provider,
                spread_provider=args.spread_provider,
                benchmark=args.benchmark,
                crisis_windows=args.crisis,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"❌ Pipeline failed for {symbol}: {exc}")
            continue
        if metrics:
            all_metrics.append(metrics)

    if all_metrics:
        _export_watchlist_results(all_metrics, Path(args.output_dir))
import argparse
import json
import os
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
from src.core.metrics import MetricsCollector
from src.risk.config import default_risk_config
from src.risk.engine import RiskEngine
from src.risk.models import Position as RiskPosition

from .intraday_backtester import IntradayBacktester
from .intraday_data_fetcher import IntradayDataFetcher
from .intraday_signal_generator import IntradaySignalGenerator


def _parse_list(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_float_list(value: Optional[str]) -> Optional[List[float]]:
    if not value:
        return None
    return [float(item) for item in value.split(",") if item]


def main() -> None:
    parser = argparse.ArgumentParser(description="Intraday mean-reversion runner")
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Return OK and exit for monitoring probes.",
    )
    parser.add_argument("--ticker", default="ES=F")
    parser.add_argument("--period", default="180d", help="yfinance lookback period")
    parser.add_argument("--interval", default="1h", help="Bar interval (1h, 5m, etc.)")
    parser.add_argument(
        "--provider",
        default="yfinance",
        choices=["yfinance", "finnhub", "polygon"],
        help="Data provider for intraday bars.",
    )
    parser.add_argument("--style", choices=["rare", "frequent"], default="rare")
    parser.add_argument(
        "--confirmations",
        help="Comma-separated confirmations (volume,divergence,support)",
    )
    parser.add_argument(
        "--support_levels",
        help="Comma-separated support/resistance levels for confirmation checks",
    )
    parser.add_argument(
        "--allow_breakout",
        action="store_true",
        help="Allow breakout logic during trending regimes",
    )
    parser.add_argument(
        "--output",
        help="Optional path to dump metrics JSON.",
    )
    args = parser.parse_args()

    if args.healthcheck:
        print("OK")
        return

    metrics_collector = MetricsCollector(enable=os.getenv("METRICS_ENABLED") == "1")
    metrics_collector.counter("intraday_run_start", ticker=args.ticker, provider=args.provider)
    start_time = time.time()
    risk_engine = RiskEngine(default_risk_config())

    fetcher = IntradayDataFetcher()
    data = fetcher.fetch(
        args.ticker,
        period=args.period,
        interval=args.interval,
        provider=args.provider,
    )
    if data.empty:
        raise SystemExit(f"No data returned for {args.ticker}")

    latest_px = float(data["Close"].iloc[-1])
    positions = [RiskPosition(ticker=args.ticker, qty=1.0, price=latest_px, sector=None, beta=1.0)]
    risk = risk_engine.check_limits(positions, nav=100000.0, strategy="intraday", portfolio="default")
    if risk["decision"] == "block":
        raise SystemExit("Risk block before intraday run: " + "; ".join([b.message for b in risk["breaches"] if b.severity == "block"]))
    if risk["decision"] == "warn":
        for b in risk["breaches"]:
            if b.severity == "warn":
                print(f"⚠️ Risk warning: {b.level}:{b.name} -> {b.message}")

    generator = IntradaySignalGenerator()
    confirmations = _parse_list(args.confirmations)
    supports = _parse_float_list(args.support_levels)

    signals = generator.generate_signal(
        data,
        style=args.style,
        confirmations=confirmations,
        support_levels=supports,
        allow_breakout=args.allow_breakout,
    )
    backtester = IntradayBacktester()
    metrics = backtester.run_backtest(data, signals=signals)

    print(f"Ticker: {args.ticker}")
    print(f"Trades: {metrics['trade_count']}, Sharpe: {metrics['sharpe']:.2f}")
    print(f"Final equity: ${metrics['final_value']:,.0f}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, default=_json_default)

    metrics_collector.timer(
        "intraday_run_runtime_s",
        time.time() - start_time,
        ticker=args.ticker,
        provider=args.provider,
    )
    metrics_collector.counter("intraday_run_end", ticker=args.ticker, provider=args.provider)


def _json_default(value):
    if isinstance(value, (pd.Timestamp, )):
        return value.isoformat()
    return value


if __name__ == "__main__":
    main()


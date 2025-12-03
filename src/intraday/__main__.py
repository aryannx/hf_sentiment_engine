import argparse
import json
from pathlib import Path
from typing import List, Optional

import pandas as pd

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

    fetcher = IntradayDataFetcher()
    data = fetcher.fetch(
        args.ticker,
        period=args.period,
        interval=args.interval,
        provider=args.provider,
    )
    if data.empty:
        raise SystemExit(f"No data returned for {args.ticker}")

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


def _json_default(value):
    if isinstance(value, (pd.Timestamp, )):
        return value.isoformat()
    return value


if __name__ == "__main__":
    main()


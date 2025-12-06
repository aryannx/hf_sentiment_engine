#!/usr/bin/env python3
# src/equities/equity_aggregator_cli.py
"""
CLI interface for equity aggregator: batch-run equity pipelines on multiple tickers
with comprehensive reporting and heatmap generation.

Usage:
    python -m equities.equity_aggregator_cli --top 10
    python -m equities.equity_aggregator_cli --tickers AAPL MSFT GOOGL
    python -m equities.equity_aggregator_cli --watchlist my_watchlist.txt --output results/
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for src.* imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.equities.equity_aggregator import EquityAggregator, get_top_tickers
from src.core.compliance_engine import ComplianceEngine
from src.core.compliance_rules import default_compliance_config
from src.risk.config import default_risk_config
from src.risk.engine import RiskEngine
from src.risk.models import Position as RiskPosition
from src.exec.config import TCAConfig
from src.exec.providers.polygon_hooks import adv_lookup_polygon, spread_lookup_polygon
from src.exec.providers.finnhub_hooks import adv_lookup_finnhub, spread_lookup_finnhub


def main():
    parser = argparse.ArgumentParser(
        description="Batch-run equity sentiment pipelines across multiple tickers"
    )

    # Ticker selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--top",
        type=int,
        help="Run on top N tickers by market cap/popularity"
    )
    group.add_argument(
        "--tickers",
        nargs="+",
        help="Space-separated list of specific tickers"
    )
    group.add_argument(
        "--watchlist",
        help="Path to file with tickers (one per line)"
    )

    # Pipeline parameters
    parser.add_argument(
        "--period",
        default="1y",
        choices=["3mo", "6mo", "1y", "2y", "5y"],
        help="Historical period for analysis"
    )
    parser.add_argument(
        "--mode",
        choices=["event", "position"],
        default="position",
        help="Signal mode: 'event' = one-bar trades, 'position' = hold until exit"
    )
    parser.add_argument(
        "--credit-overlay",
        action="store_true",
        help="Apply credit sentiment position sizing"
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=5.0,
        help="Transaction cost in basis points (default: 5bps = 0.05%)"
    )

    # Analysis options
    parser.add_argument(
        "--validate-oos",
        action="store_true",
        help="Compute train vs OOS metrics (70/30 split)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum parallel workers for ticker processing"
    )

    # Output options
    parser.add_argument(
        "--output",
        default="reports/aggregator",
        help="Output directory for results"
    )
    parser.add_argument(
        "--no-heatmaps",
        action="store_true",
        help="Skip heatmap generation in HTML report"
    )
    parser.add_argument(
        "--risk-check",
        action="store_true",
        help="Enable simple pre-flight risk limit check on requested tickers."
    )
    parser.add_argument(
        "--risk-nav",
        type=float,
        default=100000.0,
        help="Assumed NAV for risk checks."
    )
    parser.add_argument(
        "--adv-provider",
        choices=["static", "polygon", "finnhub"],
        default="static",
        help="ADV source for execution/TCA estimates.",
    )
    parser.add_argument(
        "--spread-provider",
        choices=["static", "polygon", "finnhub"],
        default="static",
        help="Spread source for execution/TCA estimates.",
    )

    args = parser.parse_args()

    # Get tickers
    if args.top:
        tickers = get_top_tickers(args.top)
        print(f"📊 Running on top {args.top} tickers")
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
        print(f"📊 Running on {len(tickers)} specified tickers: {', '.join(tickers)}")
    else:
        # Load from watchlist file
        watchlist_path = Path(args.watchlist)
        if not watchlist_path.exists():
            print(f"❌ Watchlist file not found: {watchlist_path}")
            return 1

        tickers = []
        for line in watchlist_path.read_text().splitlines():
            ticker = line.strip().upper()
            if ticker and not ticker.startswith("#"):
                tickers.append(ticker)

        if not tickers:
            print(f"❌ No valid tickers found in {watchlist_path}")
            return 1

        print(f"📊 Running on {len(tickers)} tickers from watchlist")

    # Pre-trade compliance on the universe (equal notionals assumption)
    engine = ComplianceEngine(default_compliance_config())
    pretrade = engine.evaluate_universe(tickers, portfolio_value=100000.0)
    if pretrade["decision"] == "block":
        print("❌ Compliance block on universe:")
        for res in pretrade["results"]:
            if not res.passed and res.severity == "block":
                print(f"   - {res.name}: {res.message}")
        return 1
    elif any(r.severity == "warn" for r in pretrade["results"]):
        print("⚠️ Compliance warnings on universe:")
        for res in pretrade["results"]:
            if res.severity == "warn":
                print(f"   - {res.name}: {res.message}")

    # Simple risk limits check using placeholder prices (1 unit each)
    risk_engine = RiskEngine(default_risk_config())
    if args.risk_check:
        positions = [RiskPosition(ticker=t, qty=1.0, price=100.0, sector=None, beta=1.0) for t in tickers]
        risk = risk_engine.check_limits(positions, nav=args.risk_nav, strategy="equity_agg", portfolio="watchlist")
        if risk["decision"] == "block":
            print("❌ Risk block on universe:")
            for b in risk["breaches"]:
                if b.severity == "block":
                    print(f"   - {b.level}:{b.name} -> {b.message}")
            return 1
        if risk["decision"] == "warn":
            for b in risk["breaches"]:
                if b.severity == "warn":
                    print(f"⚠️ Risk warning: {b.level}:{b.name} -> {b.message}")

    # Initialize aggregator
    aggregator = EquityAggregator()

    # Store parameters for reporting
    aggregator._last_period = args.period
    aggregator._last_mode = args.mode
    aggregator._last_credit = args.credit_overlay

    # Configure ADV/spread providers
    adv_lookup = 1_000_000.0
    spread_lookup = None
    if args.adv_provider == "polygon":
        adv_lookup = adv_lookup_polygon
    elif args.adv_provider == "finnhub":
        adv_lookup = adv_lookup_finnhub
    if args.spread_provider == "polygon":
        spread_lookup = spread_lookup_polygon
    elif args.spread_provider == "finnhub":
        spread_lookup = spread_lookup_finnhub

    # Run multi-ticker analysis
    results = aggregator.run_multi_ticker(
        tickers=tickers,
        period=args.period,
        mode=args.mode,
        use_credit_overlay=args.credit_overlay,
        cost_bps=args.cost_bps,
        validate_oos=args.validate_oos,
        max_workers=args.max_workers,
        adv_lookup=adv_lookup,
        spread_lookup=spread_lookup,
    )

    # Generate reports
    output_dir = Path(args.output)
    report_paths = aggregator.generate_report(
        results,
        output_dir,
        include_heatmaps=not args.no_heatmaps
    )

    # Summary
    successful = [r for r in results if r.get("success", False)]
    failed = [r for r in results if not r.get("success", False)]

    print(f"\n{'='*60}")
    print("AGGREGATOR COMPLETE")
    print(f"{'='*60}")
    print(f"Total tickers:     {len(results)}")
    print(f"Successful:        {len(successful)}")
    print(f"Failed:            {len(failed)}")

    if successful:
        returns = [r["total_return"] for r in successful]
        sharpes = [r["sharpe_ratio"] for r in successful]

        print(f"Avg return:        {sum(returns)/len(returns):.2%}")
        print(f"Best return:       {max(returns):.2%} ({max(successful, key=lambda x: x['total_return'])['ticker']})")
        print(f"Worst return:      {min(returns):.2%} ({min(successful, key=lambda x: x['total_return'])['ticker']})")
        print(f"Avg Sharpe:        {sum(sharpes)/len(sharpes):.2f}")
        print(f"Best Sharpe:       {max(sharpes):.2f} ({max(successful, key=lambda x: x['sharpe_ratio'])['ticker']})")

    print(f"Output directory:  {output_dir.absolute()}")
    if report_paths.get("csv"):
        print(f"CSV results:       {report_paths['csv'].name}")
    print(f"JSON results:      {report_paths['json'].name}")
    print(f"HTML report:       {report_paths['html'].name}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

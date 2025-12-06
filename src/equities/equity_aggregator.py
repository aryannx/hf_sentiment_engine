# src/equities/equity_aggregator.py
"""
Multi-ticker equity aggregator: batch-run equity pipelines, aggregate metrics,
and generate heatmaps/reports for portfolio analysis.

Features:
- Run equity pipeline on top N tickers
- Aggregate performance metrics across universe
- Generate heatmaps (Sharpe, returns, win rates)
- Export comprehensive reports (CSV, JSON, HTML)
- Support for benchmark overlays (SPY, 60/40)
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import warnings

import numpy as np
import pandas as pd

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Add src/ to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from equities.equity_data_fetcher import EquityDataFetcher
from equities.equity_sentiment_analyzer import EquitySentimentAnalyzer
from equities.equity_signal_generator import EquitySignalGenerator
from equities.equity_backtester import EquityBacktester

try:
    from credit.credit_sentiment_analyzer import CreditSentimentAnalyzer
    CREDIT_AVAILABLE = True
except ImportError:
    CREDIT_AVAILABLE = False


class EquityAggregator:
    """
    Aggregates equity pipeline results across multiple tickers for portfolio analysis.
    """

    def __init__(self):
        self.fetcher = EquityDataFetcher()
        self.sentiment_analyzer = EquitySentimentAnalyzer()
        self.signal_generator = EquitySignalGenerator()
        self.backtester = EquityBacktester(initial_cash=100000)

    def run_single_ticker(
        self,
        ticker: str,
        period: str = "1y",
        mode: str = "position",
        use_credit_overlay: bool = False,
        cost_bps: float = 0.0,
        split_ratio: float = 1.0,
        validate_oos: bool = False,
        adv_lookup: Any = 1_000_000.0,
        spread_lookup: Any = None,
        benchmark: str = "SPY",
        bond_benchmark: str = "IEF",
        crisis_windows: Optional[List[Tuple[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Run complete equity pipeline for single ticker.
        Returns metrics dict or None if failed.
        """
        try:
            # 1. Fetch price data
            price_data = self.fetcher.fetch_stock_data(ticker, period=period)
            if price_data.empty:
                print(f"⚠️ No price data for {ticker}")
                return None

            # 1b. Fetch benchmark(s)
            benchmark_df = self.fetcher.fetch_stock_data(benchmark, period=period)
            bond_df = self.fetcher.fetch_stock_data(bond_benchmark, period=period)

            # 2. Get sentiment series
            start = price_data["Date"].min().strftime("%Y-%m-%d")
            end = price_data["Date"].max().strftime("%Y-%m-%d")

            daily_sent = self.sentiment_analyzer.get_daily_sentiment_series(ticker, start, end)
            if daily_sent.empty:
                sentiment_series = np.zeros(len(price_data))
            else:
                sentiment_series = (
                    daily_sent.reindex(price_data["Date"])
                    .fillna(0.0)
                    .to_numpy()
                )

            # 3. Generate signals
            signals = self.signal_generator.generate_signal(
                price_data, sentiment_series, mode=mode
            )

            # 4. Credit overlay (if requested)
            risk_multiplier = None
            if use_credit_overlay and CREDIT_AVAILABLE:
                try:
                    credit_analyzer = CreditSentimentAnalyzer()
                    credit_sent = credit_analyzer.get_daily_sentiment_series(start, end)
                    credit_sent = credit_sent.reindex(price_data["Date"]).fillna(0.0)
                    risk_multiplier = 1.0 + 0.5 * credit_sent
                except Exception:
                    pass

            # 5. Run backtest
            metrics = self.backtester.run_backtest(
                ticker,
                signals,
                price_data,
                risk_multiplier=risk_multiplier,
                cost_bps=cost_bps,
                split_ratio=split_ratio,
                validate_oos=validate_oos,
                adv_lookup=adv_lookup,
                spread_lookup=spread_lookup,
                benchmark_df=benchmark_df if not benchmark_df.empty else None,
                benchmark_name=benchmark,
                crisis_windows=crisis_windows,
            )

            # 6. Add strategy report
            strategy_report = self.signal_generator.generate_strategy_report(
                price_data, signals, sentiment_series
            )

            # 7. Package results
            result = {
                "ticker": ticker,
                "data_points": len(price_data),
                "date_range": f"{start} to {end}",
                "total_signals": strategy_report["total_signals"],
                "buy_signals": strategy_report["buy_signals"],
                "sell_signals": strategy_report["sell_signals"],
                "avg_sentiment": float(strategy_report["avg_sentiment"]),
                "win_rate": float(strategy_report["win_rate"]),
                "total_trades": strategy_report["total_trades"],
                "sharpe_ratio": float(strategy_report["sharpe_ratio"]),
                "max_drawdown": float(strategy_report["max_drawdown"]),
                "final_value": float(metrics["final_value"]),
                "total_return": float(metrics["total_return"]),
                "annualized_return": float(metrics.get("annualized_return", 0.0)),
                "volatility": float(metrics.get("volatility", 0.0)),
                "max_drawdown_pct": float(metrics.get("max_drawdown", 0.0)),
                "backtest_sharpe": float(metrics.get("sharpe", 0.0)),
                "credit_overlay": use_credit_overlay and risk_multiplier is not None,
                "mode": mode,
                "cost_bps": cost_bps,
                "success": True,
            }

            # Add OOS metrics if available
            if validate_oos and "training_metrics" in metrics:
                train_metrics = metrics["training_metrics"]
                oos_metrics = metrics.get("oos_metrics", {})

                result.update({
                    "train_total_return": float(train_metrics.get("total_return", 0)),
                    "train_sharpe": float(train_metrics.get("sharpe", 0)),
                    "oos_total_return": float(oos_metrics.get("total_return", 0)),
                    "oos_sharpe": float(oos_metrics.get("sharpe", 0)),
                })

            # Benchmark overlays
            if metrics.get("benchmark_total_return") is not None:
                result["benchmark"] = metrics.get("benchmark", benchmark)
                result["benchmark_total_return"] = float(metrics.get("benchmark_total_return", 0.0))
                result["benchmark_annualized_return"] = float(metrics.get("benchmark_annualized_return", 0.0))
                result["excess_return"] = float(metrics.get("excess_return", 0.0))
                result["corr_with_benchmark"] = float(metrics.get("corr_with_benchmark", 0.0))
                result["beta_to_benchmark"] = float(metrics.get("beta_to_benchmark", 0.0))

            # 60/40 overlay if bond data is available
            if bond_df is not None and not bond_df.empty and benchmark_df is not None and not benchmark_df.empty:
                merged = (
                    price_data[["Date"]]
                    .merge(benchmark_df[["Date", "Close"]].rename(columns={"Close": "bench"}), on="Date", how="inner")
                    .merge(bond_df[["Date", "Close"]].rename(columns={"Close": "bond"}), on="Date", how="inner")
                )
                if not merged.empty:
                    bench_ret = merged["bench"].pct_change().fillna(0.0)
                    bond_ret = merged["bond"].pct_change().fillna(0.0)
                    sixty_forty_ret = 0.6 * bench_ret + 0.4 * bond_ret
                    sixty_total = float((1 + sixty_forty_ret).prod() - 1)
                    sixty_ann = float((1 + sixty_total) ** (252 / max(len(sixty_forty_ret), 1)) - 1)
                    result["sixty_forty_total_return"] = sixty_total
                    result["sixty_forty_annualized_return"] = sixty_ann

            if metrics.get("crisis_windows"):
                result["crisis_windows"] = metrics["crisis_windows"]

            return result

        except Exception as e:
            print(f"❌ Failed {ticker}: {e}")
            return {
                "ticker": ticker,
                "success": False,
                "error": str(e),
            }

    def run_multi_ticker(
        self,
        tickers: List[str],
        period: str = "1y",
        mode: str = "position",
        use_credit_overlay: bool = False,
        cost_bps: float = 0.0,
        split_ratio: float = 1.0,
        validate_oos: bool = False,
        max_workers: int = 4,
        adv_lookup: Any = 1_000_000.0,
        spread_lookup: Any = None,
        benchmark: str = "SPY",
        bond_benchmark: str = "IEF",
        crisis_windows: Optional[List[Tuple[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run equity pipeline on multiple tickers with parallel processing.
        """
        import concurrent.futures

        results = []

        print(f"🚀 Running equity aggregator on {len(tickers)} tickers...")
        print(f"   Mode: {mode} | Period: {period} | Credit overlay: {use_credit_overlay}")
        print(f"   Cost: {cost_bps}bps | OOS validation: {validate_oos}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(
                    self.run_single_ticker,
                    ticker,
                    period,
                    mode,
                    use_credit_overlay,
                    cost_bps,
                    split_ratio,
                    validate_oos,
                    adv_lookup,
                    spread_lookup,
                    benchmark,
                    bond_benchmark,
                    crisis_windows,
                ): ticker
                for ticker in tickers
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        status = "✅" if result.get("success", False) else "❌"
                        print(f"   {status} {ticker}")
                    else:
                        print(f"   ❌ {ticker} (no result)")
                except Exception as e:
                    print(f"   ❌ {ticker} (exception: {e})")

        # Sort by success and ticker
        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]

        successful.sort(key=lambda x: x["ticker"])
        failed.sort(key=lambda x: x["ticker"])

        return successful + failed

    def create_heatmap_data(self, results: List[Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
        """
        Create heatmap-ready DataFrames from results.
        """
        if not results:
            return {}

        # Filter successful results only
        successful = [r for r in results if r.get("success", False)]
        if not successful:
            return {}

        # Performance metrics heatmap
        perf_data = []
        for r in successful:
            perf_data.append({
                "Ticker": r["ticker"],
                "Total Return": r["total_return"],
                "Annualized Return": r["annualized_return"],
                "Sharpe Ratio": r["sharpe_ratio"],
                "Win Rate": r["win_rate"],
                "Max Drawdown": r["max_drawdown"],
                "Volatility": r["volatility"],
                "Total Trades": r["total_trades"],
            })

        perf_df = pd.DataFrame(perf_data).set_index("Ticker")

        # Signal metrics heatmap
        signal_data = []
        for r in successful:
            signal_data.append({
                "Ticker": r["ticker"],
                "Buy Signals": r["buy_signals"],
                "Sell Signals": r["sell_signals"],
                "Total Signals": r["total_signals"],
                "Avg Sentiment": r["avg_sentiment"],
                "Data Points": r["data_points"],
            })

        signal_df = pd.DataFrame(signal_data).set_index("Ticker")

        return {
            "performance": perf_df,
            "signals": signal_df,
        }

    def generate_report(
        self,
        results: List[Dict[str, Any]],
        output_dir: Path,
        include_heatmaps: bool = True,
    ) -> Dict[str, Path]:
        """
        Generate comprehensive report with CSV, JSON, and HTML outputs.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Separate successful and failed results
        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]

        # CSV export
        if successful:
            df = pd.DataFrame(successful)
            csv_path = output_dir / f"equity_aggregator_{timestamp}.csv"
            df.to_csv(csv_path, index=False)

        # JSON export
        json_path = output_dir / f"equity_aggregator_{timestamp}.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_tickers": len(results),
                    "successful": len(successful),
                    "failed": len(failed),
                    "parameters": {
                        "period": getattr(self, '_last_period', '1y'),
                        "mode": getattr(self, '_last_mode', 'position'),
                        "credit_overlay": getattr(self, '_last_credit', False),
                    }
                },
                "results": results,
            }, f, indent=2, default=str)

        # HTML report
        html_path = output_dir / f"equity_aggregator_{timestamp}.html"
        self._generate_html_report(successful, failed, html_path, include_heatmaps)

        # Bundle summary (Markdown) for interview/demo
        summary_path = output_dir / f"equity_aggregator_{timestamp}_summary.md"
        self._generate_summary_markdown(successful, failed, summary_path, csv_path if successful else None, json_path, html_path)

        # Optional zip bundle
        try:
            import shutil

            base_name = output_dir / f"equity_aggregator_{timestamp}_bundle"
            shutil.make_archive(str(base_name), "zip", root_dir=output_dir)
            bundle_path = Path(str(base_name) + ".zip")
        except Exception:
            bundle_path = None

        return {
            "csv": csv_path if successful else None,
            "json": json_path,
            "html": html_path,
            "summary": summary_path,
            "bundle": bundle_path,
        }

    def _generate_html_report(
        self,
        successful: List[Dict],
        failed: List[Dict],
        output_path: Path,
        include_heatmaps: bool,
    ):
        """Generate HTML report with tables and optional heatmaps."""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Equity Aggregator Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .success {{ color: green; }}
                .failure {{ color: red; }}
                .metric {{ text-align: right; }}
            </style>
        </head>
        <body>
            <h1>📊 Equity Aggregator Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Total Tickers:</strong> {len(successful) + len(failed)}</p>
                <p><strong>Successful:</strong> <span class="success">{len(successful)}</span></p>
                <p><strong>Failed:</strong> <span class="failure">{len(failed)}</span></p>
            </div>
        """

        if successful:
            # Performance table
            html += """
            <h2>Performance Metrics</h2>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th class="metric">Total Return</th>
                    <th class="metric">Annualized Return</th>
                    <th class="metric">Sharpe Ratio</th>
                    <th class="metric">Win Rate</th>
                    <th class="metric">Max DD</th>
                    <th class="metric">Volatility</th>
                    <th class="metric">Trades</th>
                </tr>
            """

            for r in sorted(successful, key=lambda x: x.get("total_return", 0), reverse=True):
                html += f"""
                <tr>
                    <td>{r['ticker']}</td>
                    <td class="metric">{r['total_return']:.2%}</td>
                    <td class="metric">{r['annualized_return']:.2%}</td>
                    <td class="metric">{r['sharpe_ratio']:.2f}</td>
                    <td class="metric">{r['win_rate']:.1%}</td>
                    <td class="metric">{r['max_drawdown']:.1%}</td>
                    <td class="metric">{r['volatility']:.1%}</td>
                    <td class="metric">{r['total_trades']}</td>
                </tr>
                """

            html += "</table>"

        if failed:
            html += """
            <h2>Failed Tickers</h2>
            <table>
                <tr><th>Ticker</th><th>Error</th></tr>
            """
            for r in failed:
                html += f"<tr><td>{r['ticker']}</td><td class='failure'>{r.get('error', 'Unknown error')}</td></tr>"
            html += "</table>"

        html += """
        </body>
        </html>
        """

        with output_path.open("w", encoding="utf-8") as f:
            f.write(html)

    def _generate_summary_markdown(
        self,
        successful: List[Dict],
        failed: List[Dict],
        output_path: Path,
        csv_path: Optional[Path],
        json_path: Path,
        html_path: Path,
    ) -> None:
        """Produce a concise markdown summary for interview/demo packets."""
        lines = [
            "# Equity Aggregator – Summary",
            "",
            f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Total tickers: {len(successful) + len(failed)}",
            f"- Successful: {len(successful)}",
            f"- Failed: {len(failed)}",
        ]
        if successful:
            best = max(successful, key=lambda x: x.get("total_return", 0))
            worst = min(successful, key=lambda x: x.get("total_return", 0))
            lines.append(f"- Best return: {best['ticker']} ({best.get('total_return',0):.2%})")
            lines.append(f"- Worst return: {worst['ticker']} ({worst.get('total_return',0):.2%})")
            if best.get("benchmark_total_return") is not None:
                lines.append(
                    f"- Benchmark overlay ({best.get('benchmark','SPY')}): "
                    f"strategy excess vs benchmark (best): {best.get('excess_return',0):.2%}"
                )
        if csv_path:
            lines.append(f"- CSV: {csv_path.name}")
        lines.append(f"- JSON: {json_path.name}")
        lines.append(f"- HTML: {html_path.name}")

        lines.append("")
        lines.append("## Crisis Windows (if available)")
        if successful and any(r.get("crisis_windows") for r in successful):
            for r in successful:
                if r.get("crisis_windows"):
                    for c in r["crisis_windows"]:
                        lines.append(
                            f"- {r['ticker']} {c['window']}: "
                            f"ret {c['total_return']:.2%}, maxDD {c['max_drawdown']:.2%}"
                        )
        else:
            lines.append("- None recorded")

        output_path.write_text("\n".join(lines), encoding="utf-8")


def get_top_tickers(n: int = 20) -> List[str]:
    """
    Get list of top N tickers by market cap or other criteria.
    For now, returns a curated list of popular tickers.
    """
    # This could be enhanced to fetch from an API or use a more sophisticated selection
    top_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX",
        "BABA", "ORCL", "CRM", "AMD", "INTC", "UBER", "SPOT", "PYPL",
        "SQ", "SHOP", "ZOOM", "DOCU"
    ][:n]

    return top_tickers

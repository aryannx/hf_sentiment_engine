# tests/test_equity_aggregator.py
"""
Unit tests for equity aggregator functionality.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from src.equities.equity_aggregator import EquityAggregator, get_top_tickers


class TestEquityAggregator:
    """Test EquityAggregator functionality."""

    @pytest.fixture
    def aggregator(self):
        """Create aggregator instance."""
        return EquityAggregator()

    @pytest.fixture
    def mock_price_data(self):
        """Create mock price data."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        return pd.DataFrame({
            "Date": dates,
            "Close": np.random.uniform(100, 200, 100),
            "SMA_20": np.random.uniform(95, 195, 100),
            "SMA_50": np.random.uniform(90, 190, 100),
            "RSI": np.random.uniform(20, 80, 100),
        })

    def test_init(self, aggregator):
        """Test aggregator initialization."""
        assert aggregator.fetcher is not None
        assert aggregator.sentiment_analyzer is not None
        assert aggregator.signal_generator is not None
        assert aggregator.backtester is not None

    def test_run_single_ticker_success(self, aggregator):
        """Test successful single ticker run."""
        # Mock the fetcher method directly
        mock_data = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=10),
            "Close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "SMA_20": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
            "SMA_50": [98, 99, 100, 101, 102, 103, 104, 105, 106, 107],
            "RSI": [50] * 10,
        })

        with patch.object(aggregator.fetcher, 'fetch_stock_data', return_value=mock_data), \
             patch.object(aggregator.sentiment_analyzer, 'get_daily_sentiment_series', return_value=pd.Series()), \
             patch.object(aggregator.signal_generator, 'generate_signal', return_value=np.array([0, 1, 0, -1, 0, 1, 0, -1, 0, 0])), \
             patch.object(aggregator.signal_generator, 'generate_strategy_report', return_value={
                 "total_signals": 4,
                 "buy_signals": 2,
                 "sell_signals": 2,
                 "avg_sentiment": 0.0,
                 "win_rate": 0.5,
                 "total_trades": 2,
                 "sharpe_ratio": 1.5,
                 "max_drawdown": 0.05,
             }), \
             patch.object(aggregator.backtester, 'run_backtest', return_value={
                 "final_value": 105000,
                 "total_return": 0.05,
                 "annualized_return": 0.05,
                 "volatility": 0.15,
                 "max_drawdown": 0.05,
                 "sharpe": 1.5,
             }):

            result = aggregator.run_single_ticker("TEST")

            assert result is not None
            assert result["ticker"] == "TEST"
            assert result["success"] is True
            assert result["total_return"] == 0.05
            assert result["sharpe_ratio"] == 1.5
            assert result["win_rate"] == 0.5

    def test_run_single_ticker_no_data(self, aggregator):
        """Test handling of tickers with no data."""
        with patch.object(aggregator.fetcher, 'fetch_stock_data', return_value=pd.DataFrame()):
            result = aggregator.run_single_ticker("INVALID")
            assert result is None

    def test_run_multi_ticker(self, aggregator):
        """Test multi-ticker processing."""
        with patch.object(aggregator, 'run_single_ticker') as mock_run:
            mock_run.side_effect = [
                {"ticker": "AAPL", "success": True, "total_return": 0.10},
                {"ticker": "MSFT", "success": True, "total_return": 0.05},
                None,  # Failed ticker
            ]

            results = aggregator.run_multi_ticker(
                ["AAPL", "MSFT", "INVALID"],
                max_workers=1
            )

            # Should have 2 successful results
            successful = [r for r in results if r.get("success", False)]
            assert len(successful) == 2
            assert successful[0]["ticker"] == "AAPL"
            assert successful[1]["ticker"] == "MSFT"

    def test_create_heatmap_data(self, aggregator):
        """Test heatmap data creation."""
        results = [
            {
                "ticker": "AAPL",
                "success": True,
                "total_return": 0.10,
                "annualized_return": 0.08,
                "sharpe_ratio": 1.5,
                "win_rate": 0.6,
                "max_drawdown": 0.05,
                "volatility": 0.15,
                "total_trades": 10,
                "buy_signals": 5,
                "sell_signals": 5,
                "total_signals": 10,
                "avg_sentiment": 0.1,
                "data_points": 252,
            },
            {
                "ticker": "MSFT",
                "success": True,
                "total_return": 0.05,
                "annualized_return": 0.04,
                "sharpe_ratio": 1.2,
                "win_rate": 0.55,
                "max_drawdown": 0.08,
                "volatility": 0.18,
                "total_trades": 8,
                "buy_signals": 4,
                "sell_signals": 4,
                "total_signals": 8,
                "avg_sentiment": -0.05,
                "data_points": 252,
            }
        ]

        heatmaps = aggregator.create_heatmap_data(results)

        assert "performance" in heatmaps
        assert "signals" in heatmaps

        perf_df = heatmaps["performance"]
        assert len(perf_df) == 2
        assert "AAPL" in perf_df.index
        assert "MSFT" in perf_df.index
        assert "Total Return" in perf_df.columns
        assert "Sharpe Ratio" in perf_df.columns

    def test_generate_report(self, aggregator, tmp_path):
        """Test report generation."""
        results = [
            {
                "ticker": "AAPL",
                "success": True,
                "total_return": 0.10,
                "annualized_return": 0.08,
                "sharpe_ratio": 1.5,
                "win_rate": 0.6,
                "max_drawdown": 0.05,
                "volatility": 0.15,
                "total_trades": 10,
                "buy_signals": 5,
                "sell_signals": 5,
                "total_signals": 10,
                "avg_sentiment": 0.1,
                "data_points": 252,
                "date_range": "2023-01-01 to 2023-12-31",
                "final_value": 110000,
                "backtest_sharpe": 1.5,
                "credit_overlay": False,
                "mode": "position",
                "cost_bps": 5.0,
            }
        ]

        report_paths = aggregator.generate_report(results, tmp_path)

        assert "csv" in report_paths
        assert "json" in report_paths
        assert "html" in report_paths

        # Check files exist
        assert report_paths["csv"].exists()
        assert report_paths["json"].exists()
        assert report_paths["html"].exists()

        # Check CSV content
        df = pd.read_csv(report_paths["csv"])
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "AAPL"

        # Check JSON content
        import json
        with report_paths["json"].open() as f:
            json_data = json.load(f)
        assert json_data["metadata"]["successful"] == 1
        assert len(json_data["results"]) == 1


def test_get_top_tickers():
    """Test top tickers selection."""
    tickers = get_top_tickers(5)
    assert len(tickers) == 5
    assert all(isinstance(t, str) for t in tickers)
    assert all(len(t) > 0 for t in tickers)

    # Test larger request gets capped
    all_tickers = get_top_tickers(100)
    assert len(all_tickers) <= 20  # Should be capped at available tickers

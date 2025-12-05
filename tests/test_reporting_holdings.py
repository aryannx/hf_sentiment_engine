from src.reporting.holdings import holdings_snapshot, top_holdings
import pandas as pd


def test_holdings_snapshot_and_top():
    positions = {"AAPL": 10, "MSFT": 5}
    prices = {"AAPL": 100, "MSFT": 200}
    df = holdings_snapshot(positions, prices)
    assert "weight" in df.columns
    top = top_holdings(df, n=1)
    assert len(top) == 1
    # MSFT has higher market value (5*200=1000) vs AAPL (10*100=1000) equal, so ticker order may vary
    assert top.iloc[0]["ticker"] in {"MSFT", "AAPL"}


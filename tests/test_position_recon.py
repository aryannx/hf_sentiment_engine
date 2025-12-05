from src.data.position_recon import reconcile_positions
import pandas as pd
from pathlib import Path


def test_reconcile_positions_detects_break(tmp_path: Path):
    broker = tmp_path / "broker.csv"
    broker.write_text("ticker,qty,price\nAAPL,5,100\n", encoding="utf-8")
    breaks = reconcile_positions({"AAPL": 10}, str(broker))
    assert breaks


from pathlib import Path
import json

from risk.monitor import RiskMonitor, _load_positions
from risk.models import Position


def test_monitor_evaluate_snapshot(tmp_path: Path):
    snapshot = tmp_path / "positions.json"
    snapshot.write_text(
        json.dumps([{"ticker": "AAPL", "qty": 1, "price": 100, "sector": "TECH"}]),
        encoding="utf-8",
    )
    monitor = RiskMonitor(nav=100000.0)
    positions = _load_positions(snapshot)
    result = monitor.evaluate_snapshot(positions)
    assert result["decision"] in ("pass", "warn", "block")


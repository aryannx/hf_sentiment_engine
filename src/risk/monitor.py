from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd

from risk.config import default_risk_config, RiskConfig
from risk.engine import RiskEngine
from risk.models import Position
from core.metrics import MetricsCollector
from core.notifier import notify
from core.logging_utils import get_json_logger


def _load_positions(path: Path) -> List[Position]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".json", ".jsonl"}:
        data = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix.lower() in {".csv"}:
        df = pd.read_csv(path)
        data = df.to_dict(orient="records")
    else:
        raise ValueError(f"Unsupported snapshot format: {path.suffix}")
    positions: List[Position] = []
    for row in data:
        positions.append(
            Position(
                ticker=row["ticker"],
                qty=float(row["qty"]),
                price=float(row["price"]),
                sector=row.get("sector"),
                beta=float(row.get("beta", 1.0)),
                delta=float(row.get("delta", 0.0)),
                gamma=float(row.get("gamma", 0.0)),
                vega=float(row.get("vega", 0.0)),
            )
        )
    return positions


class RiskMonitor:
    def __init__(
        self,
        risk_config: Optional[RiskConfig] = None,
        nav: float = 100000.0,
        metrics: Optional[MetricsCollector] = None,
        alert: bool = False,
    ):
        self.engine = RiskEngine(risk_config or default_risk_config())
        self.nav = nav
        self.metrics = metrics or MetricsCollector(enable=False)
        self.alert = alert
        self.logger = get_json_logger("risk.monitor")

    def evaluate_snapshot(self, positions: List[Position]):
        return self.engine.check_limits(positions, nav=self.nav, strategy="monitor", portfolio="monitor")

    def run_once(self, snapshot_path: Path):
        positions = _load_positions(snapshot_path)
        result = self.evaluate_snapshot(positions)
        self.logger.info("risk_snapshot", extra={"extra_fields": {"decision": result["decision"], "breaches": [b.__dict__ for b in result["breaches"]]}})
        self.metrics.counter("risk_snapshot_checked", decision=result["decision"])
        if result["decision"] == "block" and self.alert:
            notify("Risk block detected", level="error")
        return result

    def loop(self, snapshot_path: Path, interval_seconds: int = 60, iterations: int = 1):
        for _ in range(iterations):
            self.run_once(snapshot_path)
            time.sleep(interval_seconds)


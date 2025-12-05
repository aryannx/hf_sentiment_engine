from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Dict, List

from src.middle_office.recon import ReconciliationEngine


def load_broker_csv(path: Path) -> Dict[str, float]:
    df = pd.read_csv(path)
    pos = {}
    for _, row in df.iterrows():
        pos[row["ticker"]] = pos.get(row["ticker"], 0.0) + row["qty"]
    return pos


def reconcile_positions(fund_positions: Dict[str, float], broker_csv: str, cust_csv: str | None = None) -> List:
    broker_pos = load_broker_csv(Path(broker_csv)) if broker_csv else {}
    cust_pos = load_broker_csv(Path(cust_csv)) if cust_csv else broker_pos
    engine = ReconciliationEngine()
    return engine.reconcile(fund_positions, broker_pos, cust_pos)


from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class PaperOrder:
    ticker: str
    side: str
    qty: float
    px: float
    timestamp: str


class AlpacaPaperExecutor:
    """
    Prototype paper route for intraday signals.
    Currently logs orders locally (no live API calls) to keep workflows offline/real-data-only.
    """

    def __init__(self, log_dir: Path = Path("logs/intraday_orders")) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def submit_orders(self, orders: List[PaperOrder]) -> None:
        path = self.log_dir / f"orders_{datetime.utcnow().date()}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            for o in orders:
                f.write(json.dumps(o.__dict__) + "\n")

    @staticmethod
    def from_env() -> "AlpacaPaperExecutor":
        # Placeholder: in future, check ALPACA keys and enable live paper API.
        _ = os.getenv("ALPACA_API_KEY")
        _ = os.getenv("ALPACA_API_SECRET")
        return AlpacaPaperExecutor()


from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.core.oms_models import Order


@dataclass
class AlpacaPaperBridge:
    log_path: Path = Path("logs/oms/alpaca_paper.jsonl")

    def send(self, order: Order) -> Dict[str, Any]:
        """Prototype: log order locally to mimic Alpaca paper submission."""
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "dest": "ALPACA",
            "order": order.__dict__,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
        return {"status": "accepted", "id": f"ALP-{order.order_id}"}


@dataclass
class FixBridgeStub:
    log_path: Path = Path("logs/oms/fix_stub.jsonl")

    def send(self, order: Order, venue: str = "IBKR") -> Dict[str, Any]:
        """Stub FIX bridge (for IBKR/Bloomberg) writing to audit log."""
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "dest": venue,
            "order": order.__dict__,
            "protocol": "FIX4.4",
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
        return {"status": "accepted", "id": f"{venue}-{order.order_id}"}


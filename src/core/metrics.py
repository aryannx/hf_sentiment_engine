from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict


class MetricsCollector:
    def __init__(self, audit_dir: Path = Path("logs/metrics"), enable: bool = False):
        self.enable = enable
        self.audit_dir = audit_dir
        if enable:
            self.audit_dir.mkdir(parents=True, exist_ok=True)

    def counter(self, name: str, value: int = 1, **tags: str) -> None:
        if not self.enable:
            return
        payload = {"ts": datetime.utcnow().isoformat(), "metric": name, "type": "counter", "value": value, "tags": tags}
        self._write(payload)

    def timer(self, name: str, seconds: float, **tags: str) -> None:
        if not self.enable:
            return
        payload = {"ts": datetime.utcnow().isoformat(), "metric": name, "type": "timer", "value": seconds, "tags": tags}
        self._write(payload)

    def timeit(self, name: str, **tags: str):
        def decorator(fn):
            def wrapper(*args, **kwargs):
                start = time.time()
                result = fn(*args, **kwargs)
                self.timer(name, time.time() - start, **tags)
                return result

            return wrapper

        return decorator

    def _write(self, payload: Dict) -> None:
        path = self.audit_dir / f"metrics_{datetime.utcnow().date()}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")


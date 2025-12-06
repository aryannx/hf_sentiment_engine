from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class MetricsCollector:
    def __init__(
        self,
        audit_dir: Path = Path("logs/metrics"),
        enable: bool = False,
        prom_path: Optional[Path] = None,
    ):
        self.enable = enable
        self.audit_dir = audit_dir
        self.prom_path = prom_path
        if enable:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            if self.prom_path:
                self.prom_path.parent.mkdir(parents=True, exist_ok=True)

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
        if self.prom_path:
            self._write_prom(payload)

    def _write_prom(self, payload: Dict) -> None:
        """
        Emit a minimal Prometheus text-format line for counters/timers.
        """
        try:
            metric = payload.get("metric")
            value = payload.get("value", 0)
            tags = payload.get("tags", {})
            label_str = ",".join(f'{k}="{v}"' for k, v in tags.items())
            line = f'{metric}{{{label_str}}} {value}\n' if label_str else f"{metric} {value}\n"
            with self.prom_path.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


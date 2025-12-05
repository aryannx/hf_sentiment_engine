from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import requests


def notify(message: str, level: str = "info", webhook_env: str = "ALERT_WEBHOOK_URL", log_dir: Path = Path("logs/alerts")) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.utcnow().isoformat(), "level": level, "message": message}

    # Write to log
    path = log_dir / f"alerts_{datetime.utcnow().date()}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")

    # Optional webhook
    url = os.getenv(webhook_env)
    if url:
        try:
            requests.post(url, json=payload, timeout=3)
        except Exception:
            pass


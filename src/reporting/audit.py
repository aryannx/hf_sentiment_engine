from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def log_event(event: str, meta: Dict[str, Any], audit_dir: Path = Path("logs/reporting")) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.utcnow().isoformat(), "event": event, "meta": meta}
    path = audit_dir / f"reporting_{datetime.utcnow().date()}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


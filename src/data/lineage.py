from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def checksum_df(df) -> str:
    try:
        # stable hash on values only
        data_bytes = df.to_csv(index=False).encode("utf-8")
    except Exception:
        data_bytes = b""
    return hashlib.md5(data_bytes).hexdigest()  # nosec


def log_lineage(source: str, payload: Dict[str, Any], audit_dir: Path = Path("logs/data_lineage")) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"lineage_{datetime.utcnow().date()}.jsonl"
    record = {"ts": datetime.utcnow().isoformat(), "source": source, **payload}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


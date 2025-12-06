from __future__ import annotations

import hashlib
import json
import sqlite3
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

    # Persist to SQLite for structured queries
    sqlite_path = audit_dir / "lineage.sqlite"
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lineage (
                ts TEXT,
                source TEXT,
                payload TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO lineage (ts, source, payload) VALUES (?, ?, ?)",
            (record["ts"], source, json.dumps(payload, default=str)),
        )
        conn.commit()
    except Exception:
        # best effort; keep JSONL as primary store
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


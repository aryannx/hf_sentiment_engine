from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class CacheEntry:
    provider: str
    symbol: str
    start: Optional[str] = None
    end: Optional[str] = None
    path: Optional[str] = None
    checksum: Optional[str] = None
    bytes: Optional[int] = None
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class CacheRegistry:
    """
    Lightweight JSONL registry for cache events.
    """

    def __init__(self, log_dir: Path = Path("logs/cache_registry")) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / "registry.jsonl"

    def record(self, entry: CacheEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def list(self) -> List[CacheEntry]:
        entries: List[CacheEntry] = []
        if not self.path.exists():
            return entries
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    entries.append(CacheEntry(**data))
                except Exception:
                    continue
        return entries


def record_cache_event(
    provider: str,
    symbol: str,
    start: Optional[str],
    end: Optional[str],
    path: Optional[str],
    checksum: Optional[str],
    bytes: Optional[int] = None,
) -> None:
    """
    Convenience helper for fetchers to log cache writes.
    """
    reg = CacheRegistry()
    reg.record(
        CacheEntry(
            provider=provider,
            symbol=symbol,
            start=start,
            end=end,
            path=path,
            checksum=checksum,
            bytes=bytes,
        )
    )


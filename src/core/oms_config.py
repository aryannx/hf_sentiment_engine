from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionConfig:
    slippage_bps: float = 5.0          # default per-fill slippage
    partial_fill_prob: float = 0.2     # chance an order is partially filled
    max_partials: int = 2              # number of partial fills before fill/cancel
    venue: str = "SIM"
    seed: Optional[int] = 42           # deterministic by default

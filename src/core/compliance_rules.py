from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional


@dataclass
class ComplianceConfig:
    max_positions: int = 25
    max_single_name_pct: float = 0.10  # 10% of portfolio notional
    max_gross_notional: float = 1_000_000.0
    max_leverage: float = 2.0
    max_turnover_pct: float = 200.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RuleResult:
    name: str
    passed: bool
    severity: str  # "block" | "warn"
    message: str
    details: Optional[Dict] = None


def default_compliance_config() -> ComplianceConfig:
    """
    Default, conservative-but-not-blocking configuration for demos/backtests.
    """
    return ComplianceConfig()


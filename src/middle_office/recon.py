from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.middle_office.models import BreakRecord, BreakSeverity, BreakStatus
from src.middle_office.storage import append_jsonl, write_csv


class ReconciliationEngine:
    """
    Compare fund vs broker vs custodian positions/cash and flag breaks.
    """

    def __init__(self, materiality: float = 1e-6, audit_dir="logs/middle_office"):
        from pathlib import Path

        self.materiality = materiality
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def reconcile(
        self,
        fund_positions: Dict[str, float],
        broker_positions: Dict[str, float],
        cust_positions: Dict[str, float],
        fund_cash: float = 0.0,
        broker_cash: float = 0.0,
        cust_cash: float = 0.0,
    ) -> List[BreakRecord]:
        breaks: List[BreakRecord] = []
        all_tickers = set(fund_positions) | set(broker_positions) | set(cust_positions)
        as_of = datetime.utcnow()

        for t in all_tickers:
            f = fund_positions.get(t, 0.0)
            b = broker_positions.get(t, 0.0)
            c = cust_positions.get(t, 0.0)
            diff = max(abs(f - b), abs(f - c))
            if diff > self.materiality:
                severity = BreakSeverity.BLOCK if diff > self.materiality * 5 else BreakSeverity.WARN
                br = BreakRecord(
                    as_of=as_of,
                    ticker=t,
                    category="qty",
                    fund_value=f,
                    broker_value=b,
                    custodian_value=c,
                    materiality=self.materiality,
                    severity=severity,
                )
                breaks.append(br)
                self._audit(br)

        # Cash breaks
        cash_diff = max(abs(fund_cash - broker_cash), abs(fund_cash - cust_cash))
        if cash_diff > self.materiality:
            severity = BreakSeverity.BLOCK if cash_diff > self.materiality * 5 else BreakSeverity.WARN
            br = BreakRecord(
                as_of=as_of,
                ticker="CASH",
                category="cash",
                fund_value=fund_cash,
                broker_value=broker_cash,
                custodian_value=cust_cash,
                materiality=self.materiality,
                severity=severity,
            )
            breaks.append(br)
            self._audit(br)

        # Export CSV summary
        csv_path = self.audit_dir / f"recon_{as_of.date()}.csv"
        write_csv(csv_path, [asdict(b) for b in breaks])
        return breaks

    def reconcile_multi(
        self,
        fund_positions: Dict[str, float],
        brokers: Dict[str, Dict[str, float]],
        custodians: Dict[str, Dict[str, float]],
        fund_cash: float = 0.0,
        broker_cash: Dict[str, float] | None = None,
        cust_cash: Dict[str, float] | None = None,
    ) -> List[BreakRecord]:
        """Aggregate multiple brokers/custodians and run recon."""
        agg_broker = self._aggregate_positions(brokers)
        agg_cust = self._aggregate_positions(custodians)
        broker_cash_total = sum((broker_cash or {}).values())
        cust_cash_total = sum((cust_cash or {}).values())
        return self.reconcile(fund_positions, agg_broker, agg_cust, fund_cash, broker_cash_total, cust_cash_total)

    def mark_resolved(self, break_record: BreakRecord, resolution: str) -> None:
        break_record.status = BreakStatus.RESOLVED
        break_record.resolution = resolution
        self._audit_resolution(break_record)

    def _audit(self, br: BreakRecord) -> None:
        append_jsonl(self.audit_dir / "recon_breaks.jsonl", asdict(br))

    def _audit_resolution(self, br: BreakRecord) -> None:
        append_jsonl(self.audit_dir / "recon_resolved.jsonl", asdict(br))

    @staticmethod
    def _aggregate_positions(sources: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        agg: Dict[str, float] = {}
        for _, pos in (sources or {}).items():
            for t, q in pos.items():
                agg[t] = agg.get(t, 0.0) + q
        return agg


from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Dict, List

import pandas as pd

from src.middle_office.models import BreakRecord
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
            if max(abs(f - b), abs(f - c)) > self.materiality:
                br = BreakRecord(
                    as_of=as_of,
                    ticker=t,
                    category="qty",
                    fund_value=f,
                    broker_value=b,
                    custodian_value=c,
                    materiality=self.materiality,
                )
                breaks.append(br)
                self._audit(br)

        # Cash breaks
        if max(abs(fund_cash - broker_cash), abs(fund_cash - cust_cash)) > self.materiality:
            br = BreakRecord(
                as_of=as_of,
                ticker="CASH",
                category="cash",
                fund_value=fund_cash,
                broker_value=broker_cash,
                custodian_value=cust_cash,
                materiality=self.materiality,
            )
            breaks.append(br)
            self._audit(br)

        # Export CSV summary
        csv_path = self.audit_dir / f"recon_{as_of.date()}.csv"
        write_csv(csv_path, [asdict(b) for b in breaks])
        return breaks

    def _audit(self, br: BreakRecord) -> None:
        append_jsonl(self.audit_dir / "recon_breaks.jsonl", asdict(br))


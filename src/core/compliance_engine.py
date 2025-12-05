from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src.core.compliance_rules import ComplianceConfig, RuleResult, default_compliance_config


class ComplianceEngine:
    """
    Lightweight compliance evaluator for pre/post-trade checks.
    Designed to be OMS/EMS friendly later (FIX, broker adapters).
    """

    def __init__(
        self,
        config: Optional[ComplianceConfig] = None,
        audit_dir: Path = Path("logs/compliance"),
    ):
        self.config = config or default_compliance_config()
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_orders(
        self,
        orders: List[Dict],
        portfolio_value: float,
    ) -> Dict:
        """
        Evaluate a list of proposed orders.
        Each order dict should include:
            - ticker (str)
            - notional (float, absolute size in portfolio currency)
        """
        results: List[RuleResult] = []
        cfg = self.config

        # Basic aggregates
        gross = sum(abs(o.get("notional", 0.0)) for o in orders)
        tickers = [o.get("ticker") for o in orders if o.get("ticker")]
        distinct = set(tickers)

        # Rule: max positions
        if len(distinct) > cfg.max_positions:
            results.append(
                RuleResult(
                    name="max_positions",
                    passed=False,
                    severity="block",
                    message=f"Too many positions ({len(distinct)}) > limit {cfg.max_positions}",
                    details={"positions": len(distinct), "limit": cfg.max_positions},
                )
            )
        else:
            results.append(
                RuleResult(
                    name="max_positions",
                    passed=True,
                    severity="warn",
                    message="Within position count limit",
                )
            )

        # Rule: max single-name pct
        max_allowed = cfg.max_single_name_pct * portfolio_value
        for tkr in distinct:
            notional = sum(abs(o.get("notional", 0.0)) for o in orders if o.get("ticker") == tkr)
            if notional > max_allowed:
                results.append(
                    RuleResult(
                        name="max_single_name_pct",
                        passed=False,
                        severity="block",
                        message=f"{tkr} exceeds single-name limit ({notional:.0f} > {max_allowed:.0f})",
                        details={"ticker": tkr, "notional": notional, "limit": max_allowed},
                    )
                )
                break

        # Rule: gross notional
        if gross > cfg.max_gross_notional:
            results.append(
                RuleResult(
                    name="max_gross_notional",
                    passed=False,
                    severity="block",
                    message=f"Gross {gross:.0f} exceeds limit {cfg.max_gross_notional:.0f}",
                    details={"gross": gross, "limit": cfg.max_gross_notional},
                )
            )
        else:
            results.append(
                RuleResult(
                    name="max_gross_notional",
                    passed=True,
                    severity="warn",
                    message="Within gross notional limit",
                )
            )

        # Aggregate decision
        blocked = any((not r.passed) and r.severity == "block" for r in results)
        decision = "block" if blocked else "pass"

        audit_payload = {
            "ts": datetime.utcnow().isoformat(),
            "decision": decision,
            "portfolio_value": portfolio_value,
            "orders": orders,
            "config": self.config.to_dict(),
            "results": [asdict(r) for r in results],
        }
        self._write_audit(audit_payload)

        return {"decision": decision, "results": results}

    def evaluate_universe(
        self,
        tickers: Iterable[str],
        portfolio_value: float = 100000.0,
    ) -> Dict:
        """
        Convenience: treat each ticker as equal notional slice of the portfolio.
        """
        tickers = [t for t in tickers if t]
        if not tickers:
            return {"decision": "pass", "results": []}

        per_name = portfolio_value / len(tickers)
        orders = [{"ticker": t, "notional": per_name} for t in tickers]
        return self.evaluate_orders(orders, portfolio_value)

    def post_trade_check(
        self,
        positions: List[Dict],
        portfolio_value: float,
    ) -> Dict:
        """
        Post-trade stub: currently reuses order checks on resulting positions.
        Extend later with breaks, recon, and breach workflows.
        """
        return self.evaluate_orders(positions, portfolio_value)

    def _write_audit(self, payload: Dict) -> None:
        try:
            path = self.audit_dir / f"compliance_{datetime.utcnow().date()}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        except Exception:
            # Audit must not break execution
            pass


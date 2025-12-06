from datetime import datetime

from src.middle_office.ibor import IBOR
from src.middle_office.models import CorporateAction, CashMovement, BreakSeverity
from src.middle_office.recon import ReconciliationEngine


def test_corporate_actions_dividend_and_split():
    ibor = IBOR()
    ibor.positions["AAPL"] = 100
    ibor.cash = 0

    actions = [
        CorporateAction(as_of=datetime.utcnow(), ticker="AAPL", action_type="DIVIDEND", amount=0.5),
        CorporateAction(as_of=datetime.utcnow(), ticker="AAPL", action_type="SPLIT", ratio=2.0),
    ]
    for a in actions:
        ibor.apply_corporate_action(a)

    assert ibor.cash == 50.0
    assert ibor.positions["AAPL"] == 200


def test_cash_movement():
    ibor = IBOR()
    ibor.apply_cash_movement(CashMovement(as_of=datetime.utcnow(), amount=1000))
    assert ibor.cash == 1000


def test_recon_severity_and_resolution():
    engine = ReconciliationEngine(materiality=1.0)
    fund = {"AAPL": 100}
    brokers = {"AAPL": 90}
    cust = {"AAPL": 50}
    breaks = engine.reconcile(fund, brokers, cust, fund_cash=0, broker_cash=0, cust_cash=0)
    assert breaks
    assert any(b.severity == BreakSeverity.BLOCK for b in breaks)
    br = breaks[0]
    engine.mark_resolved(br, "investigated, pending custodian update")
    assert br.status.name == "RESOLVED"


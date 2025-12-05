from src.core.compliance_engine import ComplianceEngine
from src.core.compliance_rules import ComplianceConfig


def test_pass_when_within_limits():
    cfg = ComplianceConfig(
        max_positions=5,
        max_single_name_pct=0.5,
        max_gross_notional=1_000_000,
    )
    engine = ComplianceEngine(cfg)
    orders = [
        {"ticker": "AAPL", "notional": 100_000},
        {"ticker": "MSFT", "notional": 100_000},
    ]
    res = engine.evaluate_orders(orders, portfolio_value=500_000)
    assert res["decision"] == "pass"


def test_block_on_single_name_limit():
    cfg = ComplianceConfig(
        max_positions=5,
        max_single_name_pct=0.1,
        max_gross_notional=1_000_000,
    )
    engine = ComplianceEngine(cfg)
    orders = [{"ticker": "AAPL", "notional": 200_000}]
    res = engine.evaluate_orders(orders, portfolio_value=500_000)
    assert res["decision"] == "block"
    assert any(not r.passed for r in res["results"])


def test_block_on_position_count():
    cfg = ComplianceConfig(
        max_positions=2,
        max_single_name_pct=0.5,
        max_gross_notional=1_000_000,
    )
    engine = ComplianceEngine(cfg)
    orders = [
        {"ticker": "AAPL", "notional": 10_000},
        {"ticker": "MSFT", "notional": 10_000},
        {"ticker": "GOOGL", "notional": 10_000},
    ]
    res = engine.evaluate_orders(orders, portfolio_value=100_000)
    assert res["decision"] == "block"
    assert any(r.name == "max_positions" and not r.passed for r in res["results"])


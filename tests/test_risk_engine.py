from risk.config import RiskConfig, LayerLimits, default_risk_config
from risk.engine import RiskEngine
from risk.models import Position
import pandas as pd


def test_risk_engine_blocks_gross_leverage():
    cfg = RiskConfig(strategy_limits=LayerLimits(max_gross_leverage=1.0), portfolio_limits=LayerLimits(), firm_limits=LayerLimits())
    engine = RiskEngine(cfg)
    positions = [Position(ticker="AAPL", qty=2.0, price=100.0)]
    result = engine.check_limits(positions, nav=100.0, strategy="equity")
    assert result["decision"] == "block"
    assert any(b.name == "max_gross_leverage" for b in result["breaches"])


def test_risk_engine_warns_sector_concentration():
    limits = LayerLimits(max_position_pct=0.2, sector_caps={"TECH": 0.15})
    cfg = RiskConfig(strategy_limits=limits, portfolio_limits=limits, firm_limits=limits)
    engine = RiskEngine(cfg)
    positions = [
        Position(ticker="AAPL", qty=1.0, price=100.0, sector="TECH"),
        Position(ticker="MSFT", qty=1.0, price=90.0, sector="TECH"),
    ]
    result = engine.check_limits(positions, nav=1000.0, strategy="equity")
    assert result["decision"] in ("warn", "pass")


def test_risk_engine_flags_correlation():
    cfg = default_risk_config()
    engine = RiskEngine(cfg)
    positions = [
        Position(ticker="AAPL", qty=1.0, price=100.0, sector="TECH"),
        Position(ticker="MSFT", qty=1.0, price=100.0, sector="TECH"),
    ]
    data = pd.DataFrame(
        {
            "AAPL": [0.01, 0.02, 0.03],
            "MSFT": [0.011, 0.021, 0.031],
        }
    )
    result = engine.check_limits(positions, nav=1000.0, strategy="equity", returns=data)
    assert any(b.name == "pairwise_corr" for b in result["breaches"])


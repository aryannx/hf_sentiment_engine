import numpy as np

from risk.models import Position
from risk.scenario import shock_positions, parametric_var, historical_var, run_scenarios, apply_crisis_scenarios


def test_shock_positions():
    positions = [Position(ticker="SPY", qty=1.0, price=100.0)]
    pnl = shock_positions(positions, {"SPY": -0.1})
    assert np.isclose(pnl, -10.0)


def test_var_functions():
    returns = [0.01, -0.02, 0.005, -0.03, 0.015]
    p_var = parametric_var(returns, alpha=0.95)
    h_var = historical_var(returns, alpha=0.95)
    assert p_var > 0
    assert h_var > 0


def test_run_scenarios():
    positions = [Position(ticker="AAPL", qty=1.0, price=100.0)]
    scenarios = {"shock10": {"AAPL": -0.1}}
    results = run_scenarios(positions, scenarios)
    assert results[0][0] == "shock10"
    assert np.isclose(results[0][1], -10.0)


def test_crisis_scenarios():
    positions = [Position(ticker="SPY", qty=1.0, price=100.0)]
    results = apply_crisis_scenarios(positions)
    assert results


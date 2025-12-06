from src.pms.rebalancer import Rebalancer
from src.pms.models import Portfolio, Account


def test_rebalancer_creates_orders_when_drift_exceeds_threshold():
    acct = Account(name="TestAcct", cash=100000.0, positions={"AAPL": 0})
    portfolio = Portfolio(
        name="TestPort",
        accounts=[acct],
        target_weights={"AAPL": 1.0},
        drift_threshold=0.0,
        turnover_cap=1.0,
        cash_buffer_pct=0.0,
    )
    prices = {"AAPL": 100.0}
    reb = Rebalancer()
    proposal = reb.compute_rebalance(portfolio, prices)
    assert proposal.orders
    order = proposal.orders[0]
    assert order.side == "BUY"
    assert order.qty > 0



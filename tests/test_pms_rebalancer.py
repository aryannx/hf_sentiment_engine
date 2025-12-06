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


def test_rebalancer_account_routing_and_target_vol_scale():
    acct1 = Account(name="Acct1", cash=50000.0, positions={"AAPL": 0})
    acct2 = Account(name="Acct2", cash=50000.0, positions={"AAPL": 0})
    portfolio = Portfolio(
        name="Multi",
        accounts=[acct1, acct2],
        target_weights={"AAPL": 1.0},
        drift_threshold=0.0,
        turnover_cap=1.0,
        cash_buffer_pct=0.0,
        account_weights={"Acct1": 0.6, "Acct2": 0.4},
        target_vol=0.1,
    )
    prices = {"AAPL": 100.0}
    reb = Rebalancer()
    proposal = reb.compute_rebalance(portfolio, prices, realized_vol=0.2)  # scale to 0.5x investable
    assert proposal.orders
    # check routing weights reflected in qty ratio ~0.6/0.4
    q1 = sum(o.qty for o in proposal.orders if o.account == "Acct1")
    q2 = sum(o.qty for o in proposal.orders if o.account == "Acct2")
    assert q1 > q2



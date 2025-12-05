from src.core.oms_models import Order, OrderSide, OrderStatus
from src.core.oms_simulator import ExecutionSimulator
from src.core.oms_config import ExecutionConfig


def test_full_fill_with_zero_partial_prob():
    sim = ExecutionSimulator(ExecutionConfig(slippage_bps=5.0, partial_fill_prob=0.0, max_partials=1, seed=1))
    order = Order(order_id="1", ticker="AAPL", side=OrderSide.BUY, qty=10, px=100)
    order, fills = sim.execute(order)
    assert order.status == OrderStatus.FILLED
    assert len(fills) == 1
    assert fills[0].px > order.px  # slippage applied on BUY


def test_partial_then_fill():
    sim = ExecutionSimulator(ExecutionConfig(slippage_bps=0.0, partial_fill_prob=1.0, max_partials=2, seed=1))
    order = Order(order_id="2", ticker="MSFT", side=OrderSide.SELL, qty=10, px=50)
    order, fills = sim.execute(order)
    assert order.status in (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)
    assert sum(f.qty for f in fills) <= 10



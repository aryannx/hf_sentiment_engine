from src.core.position_ledger import PositionLedger
from src.core.oms_models import Fill, OrderSide
from datetime import datetime


def make_fill(ticker, side, qty, px):
    return Fill(
        order_id="o1",
        fill_id="f1",
        ticker=ticker,
        side=side,
        qty=qty,
        px=px,
        ts=datetime.utcnow(),
    )


def test_buy_and_sell_updates_pnl():
    ledger = PositionLedger(starting_cash=1000)
    buy_fill = make_fill("AAPL", OrderSide.BUY, qty=5, px=10)
    ledger.apply_fill(buy_fill)
    assert ledger.positions["AAPL"].qty == 5
    assert ledger.cash == 1000 - 50

    sell_fill = make_fill("AAPL", OrderSide.SELL, qty=5, px=12)
    ledger.apply_fill(sell_fill)
    assert ledger.positions["AAPL"].qty == 0
    assert ledger.realized_pnl == 10  # 5 * (12-10)


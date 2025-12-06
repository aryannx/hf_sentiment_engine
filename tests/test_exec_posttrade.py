from exec.posttrade import arrival_slippage, vwap_slippage, implementation_shortfall, posttrade_metrics


def test_arrival_slippage_buy():
    bps = arrival_slippage(exec_px=101, arrival_px=100, side="buy")
    assert bps > 0


def test_posttrade_metrics_basic():
    fills = [{"px": 101, "qty": 10, "side": "buy", "arrival_px": 100, "venue": "LIT"}]
    metrics = posttrade_metrics(fills, arrival_px=100, vwap_px=100, side="buy")
    assert metrics.arrival_slippage_bps > 0
    assert "LIT" in metrics.broker_attribution


def test_posttrade_broker_attribution_multiple():
    fills = [
        {"px": 101, "qty": 5, "side": "buy", "arrival_px": 100, "venue": "LIT"},
        {"px": 100.5, "qty": 5, "side": "buy", "arrival_px": 100, "venue": "DARK"},
    ]
    metrics = posttrade_metrics(fills, arrival_px=100, vwap_px=100, side="buy")
    assert set(metrics.broker_attribution.keys()) == {"LIT", "DARK"}


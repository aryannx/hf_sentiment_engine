from exec.microstructure import spread_bps, impact_linear, depth_score


def test_spread_bps():
    assert spread_bps(99, 101) > 0


def test_impact_linear_increases_with_participation():
    low = impact_linear(1_000_000, 10_000_000)
    high = impact_linear(5_000_000, 10_000_000)
    assert high > low


def test_depth_score():
    assert depth_score(1_000_000, 10_000_000) == 0.1


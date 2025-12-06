from exec.config import TCAConfig
from exec.pretrade import estimate_slippage, pretrade_estimate


def test_estimate_slippage_scales_with_adv():
    cfg = TCAConfig()
    spread = cfg.default_spread_bps
    low_adv = estimate_slippage(notional=1_000_000, adv=2_000_000, spread_bps=spread, impact_coeff=cfg.impact.impact_coefficient)
    high_adv = estimate_slippage(notional=1_000_000, adv=10_000_000, spread_bps=spread, impact_coeff=cfg.impact.impact_coefficient)
    assert low_adv > high_adv


def test_pretrade_estimate_builds_schedule():
    cfg = TCAConfig()
    est = pretrade_estimate(500_000, 5_000_000, cfg, ticker="AAPL")
    assert len(est.schedule) == cfg.strategy.slices
    assert est.expected_slippage_bps > 0


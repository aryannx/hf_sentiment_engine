import pandas as pd

from src.pms import risk


def test_correlation_top_pairs():
    df = pd.DataFrame(
        {
            "A": [0.01, 0.02, -0.01],
            "B": [0.011, 0.019, -0.009],
            "C": [0.0, -0.01, 0.02],
        }
    )
    corr = risk.correlation_matrix(df)
    pairs = risk.top_correlations(corr, top_n=2)
    assert pairs
    # Ensure sorting by absolute correlation
    assert abs(pairs[0][2]) >= abs(pairs[1][2])


def test_target_vol_scale_cap():
    s = risk.target_vol_scale(current_vol=0.2, target_vol=0.1)
    assert 0 < s <= 2.0


def test_margin_waterfall():
    required = risk.margin_waterfall(10_000_000, [(5_000_000, 0.15), (10_000_000, 0.25)])
    assert required > 0
    assert required < 3_000_000  # sanity upper bound


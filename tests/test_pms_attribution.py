from src.pms.attribution import contribution_report, benchmark_excess


def test_contribution_report_sums_total():
    returns = {"AAPL": 0.01, "MSFT": 0.02}
    weights = {"AAPL": 0.5, "MSFT": 0.5}
    contrib = contribution_report(returns, weights)
    assert abs(contrib["total"] - (0.5 * 0.01 + 0.5 * 0.02)) < 1e-9


def test_benchmark_excess():
    assert abs(benchmark_excess(0.05, 0.02) - 0.03) < 1e-9


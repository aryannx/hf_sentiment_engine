# src/credit/credit_tuning.py
"""
Credit parameter tuning helper for IG vs HY strategy.

Runs a coarse grid over:
    - sentiment_threshold
    - z_window
    - z_threshold

and prints Sharpe / Max DD / trades for each combination, sorted by Sharpe.
"""

from __future__ import annotations

from itertools import product

from src.credit.credit_backtester import CreditBacktester


def run_grid(period: str = "5y") -> None:
    bt = CreditBacktester(initial_cash=100000.0, notional_per_leg=1.0)

    sent_thresholds = [0.03, 0.05, 0.08]
    z_windows = [60, 120]
    z_thresholds = [0.7, 1.0, 1.3]

    combos = list(product(sent_thresholds, z_windows, z_thresholds))
    total = len(combos)

    results = []
    for i, (s_thr, zw, z_thr) in enumerate(combos, start=1):
        print(f"[{i}/{total}] running sent={s_thr:.3f}, z_win={zw}, z={z_thr:.2f} ...", flush=True)
        try:
            m = bt.run_backtest(
                period=period,
                sentiment_threshold=s_thr,
                z_window=zw,
                z_threshold=z_thr,
            )
        except Exception as e:
            print(f"    [WARN] combo failed: {e}", flush=True)
            continue

        print(
            f"    Sharpe={m['sharpe']:.2f}, "
            f"MaxDD={m['max_drawdown']:.2%}, "
            f"Trades={m['trades']}, "
            f"Ret={m['total_return']:.2%}",
            flush=True,
        )

        results.append(
            {
                "sent_thr": s_thr,
                "z_window": zw,
                "z_thr": z_thr,
                "sharpe": m["sharpe"],
                "max_dd": m["max_drawdown"],
                "trades": m["trades"],
                "total_return": m["total_return"],
            }
        )

    print("\nTop parameter combos by Sharpe:")
    if not results:
        print("  (no successful runs)")
        return

    results = sorted(results, key=lambda r: r["sharpe"], reverse=True)
    for r in results[:10]:
        print(
            f"  sent={r['sent_thr']:.3f}, "
            f"z_win={r['z_window']}, "
            f"z={r['z_thr']:.2f}  "
            f"| Sharpe={r['sharpe']:.2f}, "
            f"MaxDD={r['max_dd']:.2%}, "
            f"Trades={r['trades']}, "
            f"Ret={r['total_return']:.2%}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grid search for credit IG/HY parameters")
    parser.add_argument("--period", default="5y", help="History period (yfinance style)")
    args = parser.parse_args()

    print(f"🚀 Running credit parameter grid search over period={args.period} ...", flush=True)
    run_grid(period=args.period)

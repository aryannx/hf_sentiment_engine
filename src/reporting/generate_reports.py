from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.reporting.holdings import holdings_snapshot, top_holdings
from src.reporting.performance import performance_summary
from src.reporting.audit import log_event
from src.pms.attribution import benchmark_excess, contribution_report


def render_template(path: Path, context: dict) -> str:
    text = path.read_text(encoding="utf-8")
    for k, v in context.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text


def main():
    parser = argparse.ArgumentParser(description="Generate regulatory/investor report scaffolds (offline)")
    parser.add_argument("--positions_csv", required=False, help="CSV with columns ticker,qty,price (for holdings)")
    parser.add_argument("--equity_csv", required=False, help="CSV with equity_curve (date,value) for perf")
    parser.add_argument("--output", default="reports", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load positions
    positions = {}
    prices = {}
    if args.positions_csv and Path(args.positions_csv).exists():
        pos_df = pd.read_csv(args.positions_csv)
        for _, row in pos_df.iterrows():
            positions[row["ticker"]] = row["qty"]
            prices[row["ticker"]] = row["price"]

    # Load equity curve
    equity_curve = pd.Series(dtype=float)
    if args.equity_csv and Path(args.equity_csv).exists():
        eq_df = pd.read_csv(args.equity_csv, parse_dates=[0], index_col=0)
        equity_curve = eq_df.iloc[:, 0]

    # Holdings outputs
    holdings_df = holdings_snapshot(positions, prices)
    holdings_path = output_dir / "regulatory" / "holdings_13f_like.csv"
    if not holdings_df.empty:
        holdings_path.parent.mkdir(parents=True, exist_ok=True)
        holdings_df.to_csv(holdings_path, index=False)
    else:
        holdings_path.parent.mkdir(parents=True, exist_ok=True)
        holdings_df.to_csv(holdings_path, index=False)

    top_df = top_holdings(holdings_df, n=10)
    top_table = top_df.to_markdown(index=False) if not top_df.empty else "No holdings"

    # Performance summary
    perf = performance_summary(equity_curve) if not equity_curve.empty else {
        "total_return": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "max_drawdown": 0.0,
        "monthly_returns": {},
    }

    # Stress / crisis placeholders
    stress_pnl = 0.0
    crisis_note = "Not run"
    if not positions or not prices:
        stress_pnl = 0.0
    else:
        stress_pnl = sum(qty * prices.get(tkr, 0.0) * -0.1 for tkr, qty in positions.items())
        crisis_note = "Crisis replays not implemented; manual insert"

    # Attribution placeholder
    attribution = "Not available"
    if positions and prices and perf["total_return"] != 0:
        weights = {}
        total_mv = sum(qty * prices.get(t, 0.0) for t, qty in positions.items())
        if total_mv > 0:
            weights = {t: (qty * prices.get(t, 0.0)) / total_mv for t, qty in positions.items()}
            contrib = contribution_report(perf["monthly_returns"], weights) if perf.get("monthly_returns") else {}
            attribution = str(contrib) if contrib else "Not available"

    # Render templates
    templates_dir = Path("docs/templates")
    inv_tpl = templates_dir / "investor_letter.md"
    reg_tpl = templates_dir / "regulatory_summary.md"

    date_str = datetime.utcnow().date().isoformat()
    context_common = {
        "date": date_str,
        "total_return": f"{perf['total_return']:.2%}",
        "sharpe": f"{perf['sharpe']:.2f}",
        "sortino": f"{perf.get('sortino', 0.0):.2f}",
        "max_drawdown": f"{perf['max_drawdown']:.2%}",
        "holdings_table": holdings_df.to_markdown(index=False) if not holdings_df.empty else "No holdings",
        "top_holdings_table": top_table,
        "stress_pnl": f"{stress_pnl:,.0f}",
        "crisis_note": crisis_note,
        "attribution": attribution,
        "correlation_flags": "Not evaluated",
    }

    inv_content = render_template(
        inv_tpl,
        {
            **context_common,
            "portfolio_name": "DemoPortfolio",
            "commentary": "Placeholder commentary.",
            "outlook": "Placeholder outlook.",
        },
    )
    reg_content = render_template(reg_tpl, context_common)

    (output_dir / "investor").mkdir(parents=True, exist_ok=True)
    (output_dir / "regulatory").mkdir(parents=True, exist_ok=True)

    (output_dir / "investor" / f"investor_letter_{date_str}.md").write_text(inv_content, encoding="utf-8")
    (output_dir / "regulatory" / f"reg_summary_{date_str}.md").write_text(reg_content, encoding="utf-8")

    log_event("report_generated", {"date": date_str, "outputs": str(output_dir)})


if __name__ == "__main__":
    main()


#!/usr/bin/env bash

# Run crisis replay across a universe of tickers and emit standardized report packs.
# Default crisis windows: GFC and COVID.

set -euo pipefail

OUT_DIR="${1:-reports/crisis_replay}"
TOP_N="${TOP_N:-20}"
PERIOD="${PERIOD:-5y}"
CRISIS="${CRISIS:-2008-09-01:2009-06-30 2020-02-15:2020-04-30}"

echo "Running crisis replay for top ${TOP_N} tickers over ${PERIOD}"
echo "Crisis windows: ${CRISIS}"

python -m src.equities.equity_aggregator_cli \
  --top "${TOP_N}" \
  --period "${PERIOD}" \
  --crisis ${CRISIS} \
  --output "${OUT_DIR}" \
  --benchmark SPY \
  --bond-benchmark IEF

echo "Outputs written under ${OUT_DIR}"


#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
DR Tabletop Checklist (print and walk through)
1) Trigger health probes:
   - python scripts/health_probe.py --cmd "python -m src.main --healthcheck"
   - python scripts/health_probe.py --cmd "python -m src.credit.credit_backtester --healthcheck"
   - python scripts/health_probe.py --cmd "python -m src.intraday --healthcheck"
2) Verify backups:
   - ls backups/ (or run scripts/backup.sh)
3) Check metrics/alerts:
   - tail logs/metrics/metrics_*.jsonl
   - tail logs/alerts/alerts_*.jsonl
4) Re-run data pipeline in dry mode (if available) or minimal ticker.
5) Re-run reconciliations (positions vs broker/custodian) if data present.
6) Document findings & action items.
EOF


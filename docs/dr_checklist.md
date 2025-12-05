# Disaster Recovery / On-Call Checklist (Scaffold)

- Verify healthchecks: `python -m src.main --healthcheck`, `python -m src.credit.credit_backtester --healthcheck`, `python -m src.intraday --healthcheck`
- Check logs for recent alerts: `logs/alerts/alerts_*.jsonl`
- Confirm metrics heartbeat files present: `logs/metrics/metrics_*.jsonl`
- Validate backups exist and are recent: `ls backups/`
- Run snapshot if needed: `bash scripts/backup.sh`
- Confirm data caches available: `data/raw/`, `data/cache/`
- If batch rerun required: follow `docs/RUNBOOK.md` steps for nightly flows
- Record incident timeline and actions; capture follow-ups for root cause


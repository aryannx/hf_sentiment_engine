# On-Call & Alerts (Template)

- Rotation: WEEKLY, handoff Monday 09:00 local.
- Primary: <name/email> • Secondary: <name/email>.
- Severity:
  - SEV1: trading halted / data pipeline down → page immediately.
  - SEV2: degraded data quality or elevated errors → page within 15 minutes.
  - SEV3: non-urgent issues → ticket + next-business-day follow-up.
- Alert channels: email/webhook (see `ALERT_WEBHOOK_URL`), console logs in `logs/alerts/`.
- Health probes: `python scripts/health_probe.py --cmd "python -m src.main --healthcheck"` (repeat for credit/intraday).
- Metrics: JSONL in `logs/metrics/`; Prometheus text (if enabled) at `logs/metrics/metrics.prom`.
- Escalation: if no ack in 10 minutes for SEV1/2 → escalate to secondary, then lead.
- DR tabletop: run `scripts/dr_tabletop.sh` monthly; record gaps and fixes.


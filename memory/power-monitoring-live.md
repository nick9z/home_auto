---
name: power-monitoring-live
description: Tapo power monitoring is live production infrastructure — cron + systemd depend on power/
metadata:
  type: project
---

The `power/` subproject is **running production infrastructure** as of 2026-07-12:
user crontab (00:15 collector, 07:30 phone summary) and systemd user service
`power-dashboard` (http://192.168.1.106:8091; port 8090 belongs to AI Harness).

**Why:** future sessions editing this repo must not rename/move `power/` files or
break `config.yaml` without updating crontab and the service unit.

**How to apply:** after changing `power/`, re-run `collector.py` and
`summary.py --dry-run` manually, and `systemctl --user restart power-dashboard`.
P110 gotcha: daily `get_energy_data` must be quarter-aligned (see
`tapo_client.get_daily` docstring) — related [[phone-if-local-endpoint]].

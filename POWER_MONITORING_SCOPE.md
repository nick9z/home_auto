# Tapo Power Monitoring — Project Scope

*Scoped 2026-07-12. All device capabilities below were verified live against the actual plugs, not assumed from documentation.*

## 1. Overview & goals

Capture, store, and report household power usage from the Tapo P110 smart plugs:

1. **Daily capture** — save timestamped power usage (hour-by-hour and daily totals) to a local database, permanently.
2. **Dashboard** — local web dashboard showing each device's live status and configuration, plus usage charts.
3. **Morning summary** — at **07:30** each day, push a summary of the previous day's usage to Nick's phone via phone_interface.
4. **Weekly tracking** — week-to-date usage (**week starts Monday**) compared against the previous week's total.
5. **Cost estimates** — flat rate **$0.30/kWh** shown alongside kWh everywhere (rate lives in config, easily changed).

## 2. Hardware & infrastructure inventory (verified)

### Devices — 3 × Tapo P110 metering plugs

| Alias | IP (at scan time) | Notes |
|---|---|---|
| Dryer-Laundry | 192.168.1.56 | Was drawing 2,146 W during scoping scan |
| Dryer-Rumpus | 192.168.1.197 | |
| Washing Machine | 192.168.1.94 | |

**IPs are ephemeral** (DHCP on the Deco M5 mesh) — always key devices by **alias**, re-discover IP on connection failure. Never hardcode IPs in logic; cache them only as a first-try optimisation.

### Network caveat — Deco mesh breaks broadcast discovery
`kasa discover` (UDP broadcast) returns 0 devices on this LAN. Working approach (from the existing Hermes skill `/home/nick/.hermes/skills/smart-home/tplink-smart-home/scripts/scan_lan.py`): read ARP neighbors (`ip neigh show dev enp1s0`), probe candidates unicast with `Discover.discover_single(ip, ...)`.

### Credentials & tooling
- Tapo account creds: `KASA_USERNAME` / `KASA_PASSWORD` in `~/.env` (working — Third-Party Compatibility is enabled in the Tapo app so devices use KLAP).
- python-kasa **0.10.2** already installed in venv `/home/nick/.local/share/venvs/python-kasa/` (CLI at `~/.local/bin/kasa`).
- Phone push: phone_interface bridge at `https://phone.nescolcrafts.com`.

### On-device data retention (probed on Dryer-Laundry)

| Granularity | Retention | Query |
|---|---|---|
| Live W / V / A + today & month Wh | instantaneous | `get_energy_usage` |
| Hourly Wh | **~7 days** | `get_energy_data`, `interval=60` |
| Daily Wh | **≥60 days** (partial at ~90) | `get_energy_data`, `interval=1440` |
| Monthly Wh | ≥ current year | `get_energy_data`, `interval=43200` |

## 3. Capture strategy (decided)

**Device-history only — no continuous polling.** A nightly collector pulls each plug's own meter history (exact figures) into SQLite. The dashboard reads live watts on demand.

**Backfill window: 60 days.** After downtime the collector fills missed *hourly* rows where the device still holds them (~7 days back) and missed *daily* totals for the remainder of the 60-day window. The first-ever run seeds the DB with 60 days of daily totals + 7 days of hourly.

Trade-off accepted: hour-of-day resolution, not minute-level appliance cycle curves (listed as a future option, §8).

## 4. Architecture

```
home_auto/power/
├── config.yaml          # device aliases, tariff, summary time, DB path, LAN subnet/iface
├── tapo_client.py       # alias-keyed discovery + energy queries (python-kasa)
├── collector.py         # nightly: hourly + daily Wh → power.db (idempotent, 60-day backfill)
├── summary.py           # 07:30: yesterday + week-to-date summary → phone push
├── db.py                # SQLite schema + upsert/query helpers
├── power.db             # SQLite database (created on first run)
└── dashboard/
    ├── app.py           # FastAPI app (uvicorn, LAN-bound)
    └── templates/…      # status page + charts
```

### 4.1 `config.yaml`
```yaml
devices: ["Dryer-Laundry", "Dryer-Rumpus", "Washing Machine"]   # aliases
tariff_per_kwh: 0.30          # AUD, flat rate
currency: AUD
summary_time: "07:30"
week_start: monday
backfill_days: 60
db_path: power.db
lan: { iface: enp1s0, subnet: "192.168.1" }
```

### 4.2 `tapo_client.py`
- `find_devices(aliases)` — try cached IPs first (`devices` table), else ARP-neighbor unicast sweep (pattern from `scan_lan.py`); match by alias; update cache.
- `get_live(dev)` — raw `get_energy_usage` → current W (from mW), today/month Wh, runtimes. **Note:** must use raw protocol queries; python-kasa's `energy.get_daily_stats()` raises "Device does not support periodic statistics" on the P110.
- `get_hourly(dev, start, end)` / `get_daily(dev, start, end)` — raw `get_energy_data` with `interval=60` / `1440`; returns Wh arrays aligned to returned `start_timestamp`.

### 4.3 SQLite schema (`db.py`)
```sql
devices(alias TEXT PRIMARY KEY, model TEXT, mac TEXT, last_ip TEXT,
        fw TEXT, first_seen TEXT, last_seen TEXT);
hourly_energy(alias TEXT, hour_ts TEXT, wh INTEGER,      -- hour_ts = local "YYYY-MM-DD HH:00"
              PRIMARY KEY (alias, hour_ts));
daily_energy(alias TEXT, date TEXT, wh INTEGER,           -- date = local "YYYY-MM-DD"
             PRIMARY KEY (alias, date));
```
All writes are `INSERT ... ON CONFLICT ... DO UPDATE` (idempotent; re-runs and backfills safe). Timestamps in local time (matches device's `local_time`).

### 4.4 `collector.py` — cron **00:15 daily**
1. Discover all configured devices; update `devices` table.
2. For each device: find gaps in `daily_energy` over the last `backfill_days` (60) and in `hourly_energy` over the last 7 days.
3. Pull the missing ranges via `get_energy_data`; upsert. Yesterday's 24 hourly slots + daily total are always re-pulled (covers the normal nightly case).
4. Log to `collector.log`; per-device failures don't abort the others; nonzero exit + log entry if a device was unreachable (next night's run self-heals via backfill).

### 4.5 `summary.py` — cron **07:30 daily**
Reads only SQLite (no device access → always fast, works even if a plug is offline). Computes:
- Yesterday per-device kWh + $, and household total.
- Week-to-date (Monday → yesterday) total vs **previous full week** total, with % difference.

Sends via `POST https://phone.nescolcrafts.com/api/notify`, headers `X-Api-Key: $PHONE_IF_API_KEY_HOME_AUTO`, body `{"title", "body"}` (stdlib `urllib`, pattern from `phone_interface/cli/phone-notify`). Example message:

> **Power — Sat 11 Jul: 6.2 kWh ($1.86)**
> Dryer-Laundry 4.5 kWh · Washing Machine 1.2 kWh · Dryer-Rumpus 0.5 kWh
> Week to date: 18.4 kWh ($5.52) — last week: 24.1 kWh ($7.23) (−24%)

### 4.6 `dashboard/` — FastAPI + uvicorn, LAN-bound (e.g. `0.0.0.0:8090`)
- **Devices page** — per device: live watts (queried on request), on/off state, alias, model, fw, IP, MAC, today/month kWh from the plug, last-collected timestamp from DB. Graceful "unreachable" state.
- **Usage page** — from SQLite: hourly profile chart (per day, per device), daily history bar chart (60 days), week-to-date vs last-week comparison, cost figures at the configured tariff.
- Server-rendered templates + a lightweight chart lib; no build step. LAN-only, no auth (consistent with other local services).

### 4.7 Scheduling
- Cron (user crontab): `15 0 * * *` collector, `30 7 * * *` summary — both via the python-kasa venv interpreter with `~/.env` sourced.
- Dashboard: systemd **user** service (`~/.config/systemd/user/power-dashboard.service`), enabled + lingering so it survives reboot.

## 5. Setup steps (one-time)
1. `/phone-register home_auto` — mints `PHONE_IF_API_KEY_HOME_AUTO` into `~/.env`, wires phone MCP tools, sends test push.
2. Create `home_auto/power/` per §4 (reuse the python-kasa venv; add FastAPI/uvicorn to it or a small project venv via `uv`).
3. Run `collector.py --seed` → verify 60 days of daily + 7 days of hourly data landed.
4. Install cron entries; install + start the dashboard service.
5. `git init` the project (also unblocks any future cloud/Ultraplan sessions).

## 6. Verification plan
- **Collector:** run manually; cross-check a few `daily_energy` rows against the Tapo app's Energy tab for the same days.
- **Backfill:** delete a mid-range daily row + a recent hourly row from the DB, re-run collector, confirm both restored.
- **Summary:** run `summary.py --send` manually; confirm push arrives on the phone and figures match a hand-computed query.
- **Dashboard:** open from a phone browser on the LAN; run the washing machine and confirm live watts move; check week comparison math on a known dataset.

## 7. Failure modes handled
- Device IP changed → alias re-discovery sweep.
- Device/host offline overnight → 60-day daily / 7-day hourly backfill on next run.
- Plug unreachable at summary time → summary unaffected (DB-only).
- Duplicate runs → idempotent upserts.

## 8. Future options (out of scope)
- 1-minute live sampling for appliance cycle curves.
- Time-of-use tariff support.
- Cycle detection ("dryer finished" push).
- Additional devices — add alias to `config.yaml`, nothing else changes.

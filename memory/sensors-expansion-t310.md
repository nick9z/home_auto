---
name: sensors-expansion-t310
description: home_auto sensor monitoring — BUILT & LIVE. H100 hub at 192.168.1.150, sensor_collector.py snapshots T310 temp/humidity every 30 min via cron
metadata:
  type: project
---

**STATUS 2026-07-18: BUILT & LIVE.** Sensor monitoring now runs alongside the
power monitoring. New files in `power/`: `sensor_client.py` (find hub by model
H100, read children via raw `get_child_device_list`, NO `dev.update()`) and
`sensor_collector.py` (cron `*/30 * * * *` — snapshots current temp/humidity
per T310 into new SQLite tables `sensors` + `sensor_readings`). Offline sensors
are stored as NULL temp/humidity (online=0) so they don't skew stats. Hub IP is
cached in the `devices` table (alias "Smart Hub H100", model H100) →
`db.cached_hub_ip()`. `summary.py` morning push now appends per-sensor lines
(now-reading + yesterday range + offline/low-battery warnings). Dashboard has a
`/api/sensors` endpoint + "Temperature & Humidity" cards. Verified end-to-end;
"Laundry Cupboard-Books" logging 35.6°C/27%.

**UPDATE 2026-07-25:** both T310s are online now — the second one (was
flat-battery/offline, previously showed as "Temperature Humidity Sensor") has
a battery in and is reporting 24.1°C/45% RH. Renamed it to **"Storage Room"**
via the Tapo phone app directly (the actual device/hub nickname), confirmed by
re-running `sensor_collector.py` and seeing "Storage Room" come back from the
raw `get_child_device_list` query. (An earlier config-side `sensor_names`
override in `power/config.yaml` was tried first, then removed once the app
rename confirmed working — no override needed since the source nickname is
now correct.) NOTE: hub's `get_temp_humidity_records` 24h history buffer
returned all -1000 (empty) — that's why we snapshot instead of pulling history.

---
_(original discovery notes below)_


User wants to extend home_auto beyond power monitoring to add sensor coverage
(temp/humidity/motion), starting with Tapo **T310** sensors paired to a
**Tapo H100 hub**.

**UNBLOCKED (2026-07-18): hub + sensors located.** The H100 hub is at
**192.168.1.150**, MAC `98:25:4A:ED:43:E3`, fw 1.6.1, on the `tpdeco` mesh
(rssi -23). It has 3 paired children (from `get_child_device_list`):
- **T310 "Laundry Cupboard-Books"** — ONLINE, live 35.6°C / 27% RH (this is
  the newly-added working one).
- T310 "Temperature Humidity Sensor" — OFFLINE (the old flat-battery unit).
- S200B "Tapo S200B Button" — online.

**Key discovery gotcha:** the hub WAS on 192.168.1.x the whole time; earlier
scans missed it because [[power-monitoring-live]]'s `tapo_client.find_devices`
calls `dev.update()` after `discover_single`, and on the hub `update()` runs a
big multi-request that TIMES OUT on the child query and throws — so the hub
silently dropped out of results. Port signature helped ID it: the hub answers
on port **80 only** (KLAP/HTTP); the 3 Deco nodes (74:da:88:b5:xx at .159/.204/
.227) serve 80+443; the P110 plugs are the other 1c:61:b4 / 74:fe:ce MACs.

**How to read sensors (works):** `Discover.discover_single(ip, timeout=20,
**creds)` then a RAW single query — do NOT call `dev.update()`:
`await dev.protocol.query("get_child_device_list")`. Returns child dicts with
`model`, `status`, `current_temp`, `current_humidity`, `temp_unit`,
`at_low_battery`, `rssi`, and base64 `nickname`. Same KASA_USERNAME/PASSWORD
creds from ~/.env as the plugs. Working probe scripts were in scratchpad.

**Next step (building the collector):** mirror the power/ pattern — find the
hub by MAC/alias (it's a SmartDevice model H100), pull child list, store
temp/humidity rows per sensor in SQLite, fold into the daily summary +
dashboard. Skip the offline second T310 (or flag it). No new library needed —
python-kasa already installed in power/.venv.

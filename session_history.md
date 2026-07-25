## 2026-07-18 16:20 — T310 sensor monitoring built, live & backed up

**Resume:** `cd /home/nick/ai_gen_proj/home_auto && claude --resume 1332cafe-98e7-4d78-bf4d-df8fc5c34a05`

**Did this session:**
- **Located the H100 hub** at `192.168.1.150` (MAC `98:25:4A:ED:43:E3`) — it was on the LAN all along; prior scans missed it because `dev.update()` times out on the hub's child query and throws. Identified it via port signature (hub = port 80 only; Deco nodes = 80+443) then a raw `get_device_info` / `get_child_device_list`.
- Found 3 paired children: T310 **"Laundry Cupboard-Books"** (online, ~35.6°C/27%), a 2nd T310 **"Temperature Humidity Sensor"** (offline — flat battery, user replacing), and an S200B button.
- **Built sensor monitoring** mirroring the power subsystem: `sensor_client.py` (find hub by model, read children via raw query, no `update()`), `sensor_collector.py` (30-min cron snapshot), new `sensors` + `sensor_readings` SQLite tables, hub IP cached in `devices` table.
- Wired sensors into the **morning push** (per-sensor daily min/max/avg temp + humidity range + current + offline/low-battery warnings) and added a **dashboard trend chart** (Temp/Humidity toggle, day nav, tooltips) via `/api/sensors` + `/api/sensor_history`.
- Confirmed phone push is **text-only** (PWA renders body as textContent; shared bridge) — user chose text digest + tap-through dashboard link rather than pushing an image or extending the shared bridge.
- Two commits pushed to GitHub `main`: `da32bd9` (collector) and `b8d2ae7` (chart + digest).

**Unfinished / next:**
- 2nd T310 gets a new battery — it'll auto-appear online in the collector/dashboard, no code change needed.
- Trend chart currently sparse (collection just started 16:01); fills in as the 30-min cron runs. Yesterday min/max/avg appears in the push once a full day is banked.
- Optional/deferred: a real chart *image* to the phone would need extending the shared `phone_interface` bridge (or a daily email with a rendered PNG) — user declined for now.
- Dashboard link (`http://192.168.1.106:8091`) only reachable on home wifi.

**Key files touched:**
- `power/sensor_client.py`, `power/sensor_collector.py` — new (hub discovery + 30-min snapshot collector)
- `power/db.py` — sensors + sensor_readings tables, `cached_hub_ip`, daily-stats/history helpers
- `power/summary.py` — sensor digest lines + dashboard link in morning push
- `power/dashboard/app.py` — `/api/sensors`, `/api/sensor_history`
- `power/dashboard/templates/index.html` — sensor cards + "Sensor trend" line chart
- `power/config.yaml` — `dashboard.link`
- crontab — added `*/30 * * * * … sensor_collector.py`
- `memory/sensors-expansion-t310.md`, `MEMORY.md` — updated to BUILT & LIVE

## 2026-07-16 — Sensors expansion scoped, blocked on flat T310 battery

**Resume:** `cd /home/nick/ai_gen_proj/home_auto && claude --resume 10d1563f-93a5-46e5-b489-31522bcd9beb`

**Did this session:**
- Reviewed the project: recapped the existing power-monitoring subsystem (collector/dashboard/summary, all live infra) for the user
- Scoped a new extension direction — sensors (temp/humidity/motion) — starting with a Tapo T310 the user owns, paired to an H100 hub
- Confirmed the installed python-kasa 0.10.2 already supports Tapo hub/child devices (`smartchilddevice.py`, `temperaturesensor.py`, `cli/hub.py`) — no new library needed
- Probed the LAN for the H100 hub: ping-swept + fully scanned `192.168.1.0/24` via `Discover.discover_single`; only the 3 known P110 plugs answered, hub not found
- User revealed the T310's battery is flat — that's the likely reason the hub/sensor didn't surface; aborted further scoping for this session

**Unfinished / next:**
- User to replace the T310 battery, then resume sensor scoping
- If the H100 hub still doesn't show up on a subnet scan afterward, pull its IP directly from the Tapo app's Device Info screen rather than re-scanning blind; also worth checking the Deco app in case the hub sits on a separate guest/IoT subnet
- No code changes made this session — `power/` subsystem untouched

**Key files touched:**
- `MEMORY.md`, `memory/sensors-expansion-t310.md` — new durable memory on the blocked sensor extension

## 2026-07-12 20:24 — Tapo power monitoring: scoped, built, scheduled

**Resume:** `cd /home/nick/ai_gen_proj/home_auto && claude --resume b1885869-2b5c-45b3-a061-6dfcccc75d83`

**Did this session:**
- Scoped and fully built the Tapo P110 power-monitoring system (`POWER_MONITORING_SCOPE.md` + `power/`)
- Discovered the 3 P110 plugs (Dryer-Laundry, Dryer-Rumpus, Washing Machine); probed on-device retention: hourly ~7 days, daily ≥60 days, monthly ≥1 year
- Found + fixed critical P110 quirk: daily `get_energy_data` must be quarter-aligned or the device silently returns wrong-dated values (guarded in `tapo_client.get_daily`)
- Seeded SQLite `power/power.db` with 60 days daily + 7 days hourly; verified figures against plug counters; verified gap backfill by deleting rows and re-running
- Registered `home_auto` with phone_interface (key in `~/.env` as `PHONE_IF_API_KEY_HOME_AUTO`, badge "Home Auto" #4caf50); sent + received real summary push
- Built FastAPI dashboard (live watts/status/config + daily/hourly stacked charts, tiles, cost at $0.30/kWh, light/dark, table views) — systemd user service `power-dashboard` on **http://192.168.1.106:8091** (8090 was taken by AI Harness)
- Cron installed: 00:15 collector, 07:30 summary push (both tested under bare cron env)
- `git init` on home_auto + initial commit (also unblocks Ultraplan/cloud sessions)

**Unfinished / next:**
- Nothing pending; system is autonomous. First real scheduled cycle runs tonight 00:15 / tomorrow 07:30 — worth confirming the push arrives
- Future options (scope §8): 1-min cycle sampling, time-of-use tariff, "dryer finished" push, more devices (just add alias to `power/config.yaml`)

**Key files touched:**
- `POWER_MONITORING_SCOPE.md` — build blueprint (all claims device-verified)
- `power/{config.yaml,db.py,tapo_client.py,collector.py,summary.py}` — pipeline
- `power/dashboard/{app.py,templates/index.html}` — web dashboard
- `~/.config/systemd/user/power-dashboard.service`, user crontab, `.mcp.json`, `.gitignore`

## 2026-07-12 13:30 — Camera discovery + open-vendor purchase path

**Resume:** `cd /home/nick/ai_gen_proj/camera && claude --resume 019f544a-57e0-7231-af6f-466571688ebb`

**Did this session:**
- Probed LAN camera at `192.168.1.180` — alive (ping, hostname `Smart_Camera`, MAC `30:be:29:63:9c:23` AltoBeam), **no open TCP ports**, no RTSP/ONVIF/SSDP
- Identified device: App **InstaVision**, model **HR-PW2**, firmware **7.46.137**, Camera-ID present; light-socket wireless AliExpress/Temu style
- Confirmed platform is proprietary cloud/P2P (InstaView Inc.) — marketing ONVIF not real on wire; custom app not practical without reverse engineering
- Documented how to verify real open specs (RTSP URL, port 554, VLC test, official support docs)
- Listed recommended open brands with official websites for purchase path

**Unfinished / next:**
- Choose indoor/outdoor + budget; shortlist 1–2 exact models (likely Tapo C210 or Reolink E1 Pro first)
- Purchase open RTSP/ONVIF camera and run VLC acceptance test
- Scaffold custom app stack (go2rtc/MediaMTX → WebRTC/HLS → UI)
- Optionally keep HR-PW2 only for casual InstaVision use or dispose

**Key files touched:**
- `session_history.md` — this wrap-up (created)
- `MEMORY.md` + `memory/*` — durable project facts including vendors to try

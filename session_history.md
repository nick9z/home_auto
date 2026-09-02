## 2026-09-02 — Shelly EM Mini Gen4 wired in as Hot Water; online and collecting

**Resume:** Grok session `01a06211-9f42-7c13-96cb-7ddc37f5e0b2` in
`~/.grok/sessions/%2Fhome%2Fnick%2Fai_gen_proj%2Fhome_auto/`. Prior onboard
session (found AP + joined `tpdeco`): `01a05666-8bb9-7330-a717-174cb98b6931`
(2026-08-31).

**Did this session:**
- User asked the app to recognise a new Shelly. First pass scanned the LAN
  without reading Grok recaps — wrong order. 31 Aug session had already
  joined it to `tpdeco` at **192.168.1.157**, MAC **48:F6:EE:DC:47:88**,
  model `S4EM-001PXCEU16`.
- Silent most of the day (STALE ARP then FAILED; power-cycle did not
  immediately help). Back **online 22:47**, same IP, ~1105 W / 232 V / 4.8 A.
- **Code in.** Alias **Hot Water** (MAC-keyed). `power/shelly_client.py`;
  collector + dashboard + morning summary. History from `EM1Data.GetData`
  1-min records (GetNetEnergies empty until a full hour). Saved rows:
  2026-08-31 16:00 (0 Wh), 2026-09-02 22:00 (16 Wh).
- Local web UI: **http://192.168.1.157/** (Shelly Web Admin, no auth).
  Dashboard: http://192.168.1.106:8091.

**Unfinished / next:**
- Nightly 00:15 collector will keep filling hours. Daily chart shows
  completed days only — today's 16 Wh appears there tomorrow.
- DHCP may move `.157`; key by MAC. Device UI vs our dashboard are
  different URLs.
- Do not treat `.205` / `40:f5:20:39:df:b0` as this device.

**Key files touched:**
- `power/shelly_client.py` — new
- `power/config.yaml`, `power/collector.py`, `power/db.py`,
  `power/dashboard/app.py`, `power/dashboard/templates/index.html`
- `memory/shelly-em-mini-gen4.md`, `MEMORY.md`, `memory.md`,
  `memory/power-monitoring-live.md`, `session_history.md`

## 2026-07-28 18:05 — Scoped EARU WiFi breaker (EAWCBT-J) as a possible new power-monitoring source

**Resume:** `cd /home/nick/ai_gen_proj/home_auto && claude --resume 6bf41eb8-639e-4023-ad6a-c86c421ab5c1`

**Did this session:**
- User asked about a new gadget: **EARU Electric EAWCBT-J**, WiFi smart circuit breaker, 40A tap, DIN-rail mount, controlled via the **Tuya "Smart Life"** app (not a proprietary EARU app). Confirmed via web search: leakage protection + overcurrent, 2.4GHz-only WiFi, energy monitoring (W/V/A/kWh), power-failure memory.
- User's actual goal: read its daily wattage and fold it into the existing 07:30 phone summary alongside the Tapo P110 numbers.
- Confirmed data access is possible, but flagged it's a **different integration shape** than the Tapo plugs: two paths — (1) Tuya Cloud API (link Smart Life account to a Tuya IoT developer project, query over HTTPS, no LAN dependency) or (2) local polling via `tinytuya` (extract local key, poll on LAN, same style as `tapo_client.py`).
- Key unresolved unknown: whether this device exposes a **cumulative energy datapoint** (e.g. `add_ele`) that can be diffed day-to-day like the P110's on-device `get_energy_data` history — or only **instantaneous power** (`cur_power`), which would require adding a continuous polling/integration loop that `power/` doesn't currently have (see `POWER_MONITORING_SCOPE.md` §3, "device-history only — no continuous polling").
- No code written this session — this was scoping/research only, ahead of an actual purchase/install decision.

**Unfinished / next:**
- Nothing installed yet — this was pre-purchase research.
- Once the breaker is installed: check its actual Tuya DP schema (via Tuya IoT Platform device-debug panel, or `tinytuya`'s scan/wizard) to learn which of the two data-access paths applies before writing any collector code.
- If it turns out to be instantaneous-power-only, the `power/` architecture will need a genuinely new polling component — not a drop-in alias addition like the Tapo devices get.

**Key files touched:**
- None (research/discussion only; no repo files changed this session).



**Resume:** `cd /home/nick/ai_gen_proj/home_auto && claude --resume 3aa83b5c-cfe2-4b26-a649-d912f699a41f`

**Did this session:**
- Goal: find the IP of Nick's WiFi-connected **Econova** heat pump hot water service.
- Mapped the LAN via ping sweep + ARP + reverse DNS. Every host resolved to something identifiable (bosch-dishwasher `.18`, Foxtel `.75`, Tapo H100 `.150`, P110 `.56`, Deco-M5 `.204`, Nest Hub `.184`, Chromecast `.171`, phones/iPads) **except one**.
- **Best candidate: `192.168.1.205`** — MAC `40:f5:20:39:df:b0` (Espressif OUI), DHCP hostname `ESP-39DFB0` (factory default). TTL 128, latency 2.6–95 ms = WiFi power-save.
- Full **1–65535 TCP scan: only port 45000 open** (verified stable over repeat probes). Sends no banner; silently swallows HTTP/1.0, HTTP/1.1, TLS, newline, text, JSON → proprietary binary protocol.
- UDP silent on mDNS 5353, SSDP 1900, Tuya 6666/6667, SNMP 161, NetBIOS 137, WS-Disc 3702. A **75 s passive broadcast listen saw zero packets from `.205`**, ruling out a standard Tuya/Smart Life module (those beacon ~every 5 s); other devices chattered normally so the listener worked.
- No packet capture possible: `tcpdump` present but `sudo` needs a password and `tshark` isn't installed.
- Deliberately **did not** send arbitrary binary to tcp/45000 — on a proprietary control channel a random byte sequence could act as a command, and the user asked for read-only.
- **Conclusion the user agreed with:** with no readable local API the module itself is futile. Pivot to *measuring the electricity* rather than asking the appliance. Recommended Shelly EM Gen3 + CT clamp (documented local REST/JSON + MQTT, no cloud) — or a Tapo P110 outright if the unit turns out to be plugged into a GPO rather than hardwired.

**Unfinished / next:**
- **Open question that decides everything:** is the Econova on a normal power point or hardwired on its own circuit? Plugged in → add one line to `power/config.yaml`, existing pipeline handles it. Hardwired → Shelly EM + clamp, electrician required.
- `.205` is **inference, not proof**. To confirm: read the Ecogenica owner's manual, or switch the unit off at the isolator and watch `ip neigh show dev enp1s0` for `.205` dropping out then returning (definitive), or run `sudo timeout 120 tcpdump -i enp1s0 -n -s0 host 192.168.1.205` and read the DNS names.
- Shelly AU stock/pricing not verified (sells via local resellers, not direct).
- Long-shot path if ever wanted: tcp/45000 may be how the phone app does local control, so the protocol is observable — but capturing phone→appliance traffic on a switched mesh is fiddly and it's an undocumented binary format. Poor effort-to-reward.
- Two files uncommitted (see below) — not pushed to GitHub yet.

**Key files touched:**
- `memory/hot-water-econova-ip.md` — new; candidate IP/MAC, full scan findings, three confirmation methods, monitoring pivot
- `MEMORY.md` — added pointer line, flagged UNCONFIRMED
- No code changed. Scan scripts were throwaway, left in the session scratchpad.

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

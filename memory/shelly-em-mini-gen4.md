---
name: shelly-em-mini-gen4
description: Shelly EM Mini Gen4 alias Hot Water, MAC 48:F6:EE:DC:47:88 — online at 192.168.1.157, local web UI, wired into power/
metadata:
  type: project
---

## Identity

| | |
|---|---|
| Product | Shelly EM Mini Gen4 |
| Model | `S4EM-001PXCEU16` |
| Device id | `shellyemminig4-48f6eedc4788` |
| MAC | `48:F6:EE:DC:47:88` (AP BSSID was `48:F6:EE:DC:47:89`) |
| Firmware when last seen | `1.7.0-miniemg4prod0` |
| Alias in `power/config.yaml` | **Hot Water** |
| Setup AP SSID | `ShellyEMMiniG4-48F6EEDC4788` (open, factory IP `192.168.33.1`) |
| Home Wi-Fi | `tpdeco` (2.4 GHz). Creds: `WIFI_SSID_TPDECO` / `WIFI_PASSWORD_TPDECO` in `~/.env` |
| Last confirmed LAN IP | **`192.168.1.157`** on 2026-08-31 (DHCP — do not hardcode) |
| IPv6 link-local | `fe80::4af6:eeff:fedc:4788` (from MAC) |

**Key by MAC, never by IP.** Deco mesh DHCP moves it.

Do **not** confuse with `192.168.1.205` / MAC `40:f5:20:39:df:b0` (Econova candidate, Espressif `ESP-39DFB0`). Related [[hot-water-econova-ip]].

## Status (2026-09-02 late)

Joined to `tpdeco` 2026-08-31 from its setup AP (Grok session
`01a05666-8bb9-7330-a717-174cb98b6931`). Went silent for most of 2026-09-02
(STALE ARP then FAILED; power-cycle did not immediately help).

**Back online 2026-09-02 22:47** at **`192.168.1.157`**, same MAC, still on
`tpdeco` (RSSI −42). Live then: **232 V, 4.76 A, ~1105 W**. Local web UI:
**http://192.168.1.157/** (Shelly Web Admin, `auth_en: false`). Dashboard:
http://192.168.1.106:8091.

History is `EM1Data.GetData` 1-min records, not `GetNetEnergies`. First
saved rows: 2026-08-31 16:00 (0 Wh), 2026-09-02 22:00 (16 Wh). Collector
writes today-so-far on each run.

## How to find it next time

1. **Read this file and Grok session recaps first** — do not start with a
   blind LAN scan. Prior Grok sessions under
   `~/.grok/sessions/%2Fhome%2Fnick%2Fai_gen_proj%2Fhome_auto/`.
2. Cached IP then MAC match:
   ```
   cd /home/nick/ai_gen_proj/home_auto/power
   uv run python -c "import db,shelly_client; c=db.load_config(); print(shelly_client.find_devices(db.shelly_wanted(c), db.cached_ips(db.connect(c)), c['lan']))"
   ```
   `find_devices` = cached IP → ARP neighbors → unicast HTTP sweep matching MAC.
3. Direct probes: `http://<ip>/rpc/Shelly.GetDeviceInfo` must be JSON with
   `"mac":"48F6EEDC4788"`. Tapo plugs return fake HTML `200 OK` on `/shelly`
   — ignore those.
4. Wi-Fi: `nmcli device wifi rescan ifname wlo1` then look for
   `ShellyEMMiniG4-48F6EEDC4788`. If present, join `wlo1` with a static
   `192.168.33.10/24` (open AP, `ipv4.never-default yes`) and call
   `http://192.168.33.1/rpc/...`. Rejoin `tpdeco` via `Wifi.SetConfig` using
   `~/.env` (do not print the password). Then disable the AP and reboot.
5. mDNS (`_shelly._tcp`, `shellyemminig4-48f6eedc4788.local`) is unreliable
   on this Deco mesh — do not trust a silent mDNS result.
6. If the phone sees the setup AP but this box does not, the meter is out
   of range of `wlo1`; join from the phone or move closer.

## Pipeline (already wired)

| Piece | Role |
|---|---|
| `power/shelly_client.py` | MAC discovery + `EM1.GetStatus` live W + `EM1Data.GetNetEnergies` hourly Wh |
| `power/collector.py` | Nightly; Tapo and Shelly in parallel; Shelly miss does not skip Tapo |
| `power/dashboard/` | Live card + charts; restart `systemctl --user restart power-dashboard` after edits |
| `power/summary.py` | Morning push from SQLite only — Hot Water appears once daily rows exist |

On-device history is **~10 days** of 1-min data (not the P110's 60-day daily).
Older gaps stay empty. IPs ephemeral; MAC is the cache key.

Live: http://192.168.1.106:8091 — related [[power-monitoring-live]].

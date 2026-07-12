# Vendors / suppliers to try (open RTSP/ONVIF purchase path)

Prefer official sites + support docs over marketplace “ONVIF” claims. Verify exact model RTSP before buy.

## Primary (recommended first)

| Priority | Brand | Official website | Notes |
|----------|--------|------------------|--------|
| 1 | **TP-Link Tapo** | https://www.tapo.com/ | Best cheap starter; RTSP after local Camera Account. Models to try: **C210**, **C200**, **C110**. Streams: `rtsp://user:pass@IP:554/stream1` (HD), `/stream2` (SD) |
| 2 | **Reolink** | https://reolink.com/ | Best overall for multi-cam/custom. Indoor: **E1 Pro** / **E1 Zoom** (check standalone RTSP matrix). Outdoor PoE: **RLC-510A**, **RLC-810A**, **RLC-823A**. RTSP: `.../h264Preview_01_main` / `_sub`. Matrix: support.reolink.com CGI/RTSP/ONVIF article |
| 3 | **Amcrest** | https://amcrest.com/ | Solid outdoor/classic CCTV; Dahua OEM. RTSP: `.../cam/realmonitor?channel=1&subtype=0` (main) / `subtype=1` (sub). Prefer IP4M/IP5M series, avoid SmartHome/Link-only locks |

## Secondary / ecosystem

| Brand | Official website | Notes |
|--------|------------------|--------|
| **Imou** | https://www.imoulife.com/ | Some models enable RTSP; verify per model |
| **UniFi Protect (Ubiquiti)** | https://ui.com/ · store: https://store.ui.com/ | Premium; best if already UniFi network |
| **Dahua** | https://www.dahuasecurity.com/ | Pro OEM; Amcrest is related |
| **Hikvision** | https://www.hikvision.com/en/ | Pro RTSP/ONVIF; regional privacy/policy considerations |

## Avoid (same class as current cam)

- InstaVision / InstaView, V380-only, ICSee/Esee cloud-only, Temu/Ali “ONVIF” bulbs without published RTSP URL + VLC proof
- Battery-only P2P apps without local stream

## Purchase workflow

1. Official site → exact model → Support search `RTSP` / `ONVIF`
2. Community: VLC / Home Assistant / Frigate hits for that model
3. Buy with easy returns
4. Day-1 test: nmap port 554 open + VLC plays RTSP; else return

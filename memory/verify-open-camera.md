# How to verify a camera is truly open (not fake ONVIF)

## Real open means (on LAN, without brand cloud)

1. TCP **554** (RTSP) open
2. Documented RTSP URL + local username/password
3. Often ONVIF discovery + optional web UI
4. Plays in **VLC** with no brand app required for viewing

## Pre-buy signals

- Official support article with exact RTSP URL for the model
- Brand RTSP/ONVIF matrix (e.g. Reolink)
- Reviews: “works in VLC / Frigate / Home Assistant”
- Mains/PoE preferred over battery P2P

## Day-1 acceptance test

```bash
nmap -sT -p 80,443,554,8000,8080,8554,8899,2020 IP
# VLC: rtsp://USER:PASS@IP:554/<path>
```

Fail if: pings but no 554 / no stream → return (like HR-PW2).

## Scorecard quick rule

Buy if official RTSP + community VLC proof. Skip if only marketplace “ONVIF” badge.

## 2026-07-12 13:30 — Camera discovery + open-vendor purchase path

**Resume:** `cd /home/nick/ai_projects/camera && claude --resume 019f544a-57e0-7231-af6f-466571688ebb`

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

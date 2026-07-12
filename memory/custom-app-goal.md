# Custom app goal

- User wants own app/UI instead of vendor apps (InstaVision unsuitable)
- Build against **local RTSP/ONVIF** hardware, not reverse-engineer closed P2P
- Typical stack once open cam exists:
  - Camera RTSP → **go2rtc** or **MediaMTX** → WebRTC/HLS → custom web/mobile UI
  - Optional later: Frigate for AI events
- Next product decision needed: indoor vs outdoor, budget, pan-tilt vs fixed

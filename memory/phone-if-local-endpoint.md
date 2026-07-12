---
name: phone-if-local-endpoint
description: phone_interface public URL is Cloudflare-WAF-blocked for CLI clients — use http://127.0.0.1:8787 locally
metadata:
  type: reference
---

`https://phone.nescolcrafts.com` returns **HTTP 403 (Cloudflare error 1010)** for
non-browser clients (curl, urllib, the phone-notify CLI). The bridge runs locally,
so scripts on this machine must POST to **`http://127.0.0.1:8787`** instead
(same `/api/notify` API, `X-Api-Key` header). Key for this project:
`PHONE_IF_API_KEY_HOME_AUTO` in `~/.env`.

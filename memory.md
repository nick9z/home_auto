# memory — home_auto

Canonical curated memory for agents (newest lessons first).
Legacy file `MEMORY.md` may still exist — merge useful facts here over time.

## Lessons

- 2026-09-02: Before a LAN hunt, read Grok recaps under
  `~/.grok/sessions/%2Fhome%2Fnick%2Fai_gen_proj%2Fhome_auto/` as well as
  `session_history.md` / `memory/`. The Shelly was already joined on 31 Aug;
  skipping that wasted a full scan. Tapo `/shelly` returns fake HTML 200 —
  require JSON with a matching MAC.
- 2026-09-02: Shelly EM Mini Gen4 history is `EM1Data.GetData` (1-min Wh),
  not `GetNetEnergies` (empty until a full hour exists). Collector must also
  write today-so-far or a manual run drops the current hour. Device web UI
  is `http://<ip>/` (Shelly Web Admin, no auth).

## Standing facts

- Shelly EM Mini Gen4 = alias **Hot Water**, MAC `48:F6:EE:DC:47:88`, IP
  `192.168.1.157` (DHCP). Online 2026-09-02 22:47, ~1.1 kW. Local UI
  `http://192.168.1.157/`. Playbook: `memory/shelly-em-mini-gen4.md`.
- See also MEMORY.md if present.

"""MAC-keyed discovery and energy queries for Shelly EM Mini Gen4.

Local HTTP RPC only (no cloud, no SDK). Broadcast/mDNS is unreliable on the
Deco mesh, so devices are found by cached IP, then ARP neighbors, then a
unicast HTTP sweep, matched by MAC. Never hardcode IPs in callers.

Energy history comes from EM1Data.GetData (1-minute active Wh, aggregated
to hours). GetNetEnergies stays empty until a full hour exists. On-device
retention is about 10 days of 1-minute samples — shorter than the P110's
60-day daily window, so older gaps stay empty until the nightly collector
has been running.
"""

from __future__ import annotations

import json
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

PROBE_TIMEOUT = 3
RPC_TIMEOUT = 20
SWEEP_CONCURRENCY = 64
HTTP_PORT = 80


def _norm_mac(mac: str) -> str:
    return mac.replace(":", "").replace("-", "").replace(" ", "").upper()


def _fmt_mac(mac: str) -> str:
    n = _norm_mac(mac)
    return ":".join(n[i : i + 2] for i in range(0, 12, 2)) if len(n) == 12 else mac


def rpc(ip: str, method: str, params: dict | None = None, timeout: float = RPC_TIMEOUT) -> Any:
    """Call a Shelly gen2 HTTP RPC method. Returns the `result` object, or the
    raw body if the device returned a bare payload (GetDeviceInfo)."""
    url = f"http://{ip}/rpc/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "home_auto-shelly"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    if isinstance(body, dict) and "result" in body and "id" in body:
        return body["result"]
    if isinstance(body, dict) and body.get("code") and "message" in body:
        raise RuntimeError(f"{method} on {ip}: {body['message']}")
    return body


def _tcp_open(ip: str, port: int = HTTP_PORT, timeout: float = 0.5) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except OSError:
            pass


def _probe(ip: str) -> dict | None:
    if not _tcp_open(ip, timeout=0.5):
        return None
    try:
        info = rpc(ip, "Shelly.GetDeviceInfo", timeout=PROBE_TIMEOUT)
    except Exception:
        return None
    if not isinstance(info, dict) or "mac" not in info:
        return None
    return {
        "ip": ip,
        "mac": _fmt_mac(info["mac"]),
        "mac_raw": _norm_mac(info["mac"]),
        "model": info.get("model") or info.get("app") or "Shelly",
        "fw": info.get("ver") or "",
        "id": info.get("id") or "",
        "name": info.get("name"),
        "app": info.get("app"),
    }


def _arp_ips(iface: str, subnet: str) -> list[str]:
    out = subprocess.run(
        ["ip", "neigh", "show", "dev", iface], capture_output=True, text=True
    ).stdout
    ips = []
    for line in out.splitlines():
        parts = line.split()
        if not parts or not parts[0].startswith(subnet + "."):
            continue
        if "FAILED" in parts or "INCOMPLETE" in parts:
            continue
        ips.append(parts[0])
    return ips


def find_devices(wanted: dict[str, str], cached: dict, lan: dict) -> dict[str, dict]:
    """Return {alias: device-record} for every configured Shelly we can reach.

    `wanted` is {alias: mac}. Cached IPs are tried first (keyed by alias).
    """
    if not wanted:
        return {}
    want_mac = {_norm_mac(mac): alias for alias, mac in wanted.items()}
    found: dict[str, dict] = {}

    def take(rec: dict | None) -> None:
        if rec is None:
            return
        alias = want_mac.get(rec["mac_raw"])
        if alias and alias not in found:
            rec = dict(rec)
            rec["alias"] = alias
            found[alias] = rec

    cached_ips = [ip for a, ip in cached.items() if a in wanted and ip]
    for ip in cached_ips:
        take(_probe(ip))
        if len(found) == len(wanted):
            return found

    tried = set(cached_ips)
    arp = [ip for ip in _arp_ips(lan["iface"], lan["subnet"]) if ip not in tried]
    with ThreadPoolExecutor(max_workers=SWEEP_CONCURRENCY) as ex:
        for rec in ex.map(_probe, arp):
            take(rec)
    if len(found) == len(wanted):
        return found

    tried.update(arp)
    sweep = [
        f"{lan['subnet']}.{i}"
        for i in range(1, 255)
        if f"{lan['subnet']}.{i}" not in tried
    ]
    with ThreadPoolExecutor(max_workers=SWEEP_CONCURRENCY) as ex:
        futs = [ex.submit(_probe, ip) for ip in sweep]
        for fut in as_completed(futs):
            take(fut.result())
            if len(found) == len(wanted):
                break
    return found


def _minute_energy(ip: str, start: datetime, end: datetime) -> list[tuple[datetime, float]]:
    """1-minute active-energy samples from EM1Data.GetData (local time).

    GetNetEnergies is empty until a full hour exists, so history is built
    from the 1-min flash records. Timestamps of 0 (uninitialised slot) skipped.
    """
    ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    rows: list[tuple[datetime, float]] = []
    for _ in range(50):
        params: dict = {"id": 0, "ts": ts}
        if end_ts:
            params["end_ts"] = end_ts
        try:
            payload = rpc(ip, "EM1Data.GetData", params)
        except (urllib.error.HTTPError, RuntimeError, json.JSONDecodeError):
            break
        for block in payload.get("data") or []:
            t0 = int(block.get("ts") or 0)
            if t0 < 1_000_000_000:
                continue
            p = int(block.get("period") or 60)
            for i, vals in enumerate(block.get("values") or []):
                t = t0 + i * p
                if t < ts or t >= end_ts:
                    continue
                wh = float(vals[0]) if vals else 0.0
                rows.append((datetime.fromtimestamp(t), wh))
        nxt = payload.get("next_record_ts")
        if not nxt or int(nxt) <= ts:
            break
        ts = int(nxt)
    return rows


def get_hourly(ip: str, date: datetime) -> list[tuple[str, int]]:
    """Hourly (hour_ts, wh) rows for the given local date. Missing hours omitted."""
    day = date.replace(hour=0, minute=0, second=0, microsecond=0)
    nxt = day + timedelta(days=1)
    by_hour: dict[str, float] = {}
    for ts, wh in _minute_energy(ip, day, nxt):
        key = ts.strftime("%Y-%m-%d %H:00")
        by_hour[key] = by_hour.get(key, 0) + wh
    return [(k, int(round(v))) for k, v in sorted(by_hour.items())]


def get_daily(ip: str, start_date: datetime, end_date: datetime) -> list[tuple[str, int]]:
    """(date, wh) rows for start_date..end_date inclusive (local dates)."""
    start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    by_day: dict[str, float] = {}
    for ts, wh in _minute_energy(ip, start, end):
        key = ts.strftime("%Y-%m-%d")
        by_day[key] = by_day.get(key, 0) + wh
    return [(k, int(round(v))) for k, v in sorted(by_day.items())]


def get_live(ip: str) -> dict:
    """Instantaneous readings. today Wh is summed 1-min samples since midnight."""
    em1 = rpc(ip, "EM1.GetStatus", {"id": 0}, timeout=PROBE_TIMEOUT)
    em1data = rpc(ip, "EM1Data.GetStatus", {"id": 0}, timeout=PROBE_TIMEOUT)
    try:
        wifi = rpc(ip, "Wifi.GetStatus", timeout=PROBE_TIMEOUT)
    except Exception:
        wifi = {}

    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_wh = int(round(sum(wh for _, wh in _minute_energy(ip, midnight, now + timedelta(minutes=1)))))
    total_wh = int(round(em1data.get("total_act_energy") or 0))
    if today_wh == 0 and total_wh:
        today_wh = total_wh  # just-booted: lifetime ≈ today until a 1-min slot closes

    power = em1.get("act_power")
    return {
        "power_w": float(power) if power is not None else 0.0,
        "voltage": em1.get("voltage"),
        "current": em1.get("current"),
        "today_wh": today_wh,
        "month_wh": today_wh,  # dashboard adds earlier days from SQLite
        "total_wh": total_wh,
        "is_on": True,
        "rssi": wifi.get("rssi"),
        "local_time": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def device_info(rec: dict) -> dict:
    return {
        "alias": rec["alias"],
        "model": rec["model"],
        "mac": rec["mac"],
        "ip": rec["ip"],
        "fw": rec.get("fw") or "",
        "is_on": True,
        "rssi": rec.get("rssi"),
    }

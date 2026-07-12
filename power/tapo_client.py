"""Alias-keyed discovery and energy queries for Tapo P110 plugs.

Broadcast discovery does not work on the Deco mesh, so devices are found by
probing unicast: cached IPs first, then ARP neighbors, then a subnet sweep.
python-kasa's Energy.get_daily_stats() is unsupported on the P110, so history
comes from raw get_energy_data protocol queries (values in Wh).
"""

import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from kasa import Device, Discover

ENV_PATH = Path.home() / ".env"
PROBE_TIMEOUT = 6
SWEEP_CONCURRENCY = 64


def read_env(*names: str) -> dict:
    """Read specific vars from ~/.env without sourcing the whole file."""
    values = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() in names:
            values[key.strip()] = val.strip().strip('"').strip("'")
    missing = set(names) - set(values)
    if missing:
        raise KeyError(f"missing in ~/.env: {sorted(missing)}")
    return values


def _credentials() -> dict:
    creds = read_env("KASA_USERNAME", "KASA_PASSWORD")
    return {"username": creds["KASA_USERNAME"], "password": creds["KASA_PASSWORD"]}


async def _probe(ip: str) -> Device | None:
    try:
        dev = await Discover.discover_single(ip, timeout=PROBE_TIMEOUT, **_credentials())
        await dev.update()
        return dev
    except Exception:
        return None


def _arp_ips(iface: str, subnet: str) -> list[str]:
    out = subprocess.run(
        ["ip", "neigh", "show", "dev", iface], capture_output=True, text=True
    ).stdout
    return [line.split()[0] for line in out.splitlines() if line.startswith(subnet + ".")]


async def find_devices(aliases: list[str], cached: dict, lan: dict) -> dict[str, Device]:
    """Return {alias: connected Device} for every alias we can reach.

    Tries cached IPs, then ARP neighbors, then a full subnet sweep for any
    aliases still missing. Caller is responsible for dev.disconnect().
    """
    wanted = set(aliases)
    found: dict[str, Device] = {}

    async def try_ips(ips):
        sem = asyncio.Semaphore(SWEEP_CONCURRENCY)

        async def guarded(ip):
            async with sem:
                return await _probe(ip)

        for dev in await asyncio.gather(*(guarded(ip) for ip in ips)):
            if dev is None:
                continue
            if dev.alias in wanted and dev.alias not in found:
                found[dev.alias] = dev
            else:
                await dev.disconnect()

    cached_ips = [ip for a, ip in cached.items() if a in wanted and ip]
    if cached_ips:
        await try_ips(cached_ips)
    if wanted - set(found):
        arp = [ip for ip in _arp_ips(lan["iface"], lan["subnet"]) if ip not in cached_ips]
        await try_ips(arp)
    if wanted - set(found):
        tried = set(cached_ips) | set(_arp_ips(lan["iface"], lan["subnet"]))
        sweep = [f"{lan['subnet']}.{i}" for i in range(1, 255) if f"{lan['subnet']}.{i}" not in tried]
        await try_ips(sweep)
    return found


async def get_live(dev: Device) -> dict:
    """Instantaneous readings from get_energy_usage (power in W, energy in Wh)."""
    r = (await dev.protocol.query("get_energy_usage"))["get_energy_usage"]
    return {
        "power_w": r["current_power"] / 1000,
        "today_wh": r["today_energy"],
        "month_wh": r["month_energy"],
        "today_runtime_min": r["today_runtime"],
        "local_time": r["local_time"],
    }


async def _energy_data(dev: Device, start: datetime, end: datetime, interval: int) -> tuple[datetime, list[int]]:
    r = (
        await dev.protocol.query(
            {
                "get_energy_data": {
                    "start_timestamp": int(start.timestamp()),
                    "end_timestamp": int(end.timestamp()),
                    "interval": interval,
                }
            }
        )
    )["get_energy_data"]
    return datetime.fromtimestamp(r["start_timestamp"]), r["data"]


async def get_hourly(dev: Device, date: datetime) -> list[tuple[str, int]]:
    """24 (hour_ts, wh) rows for the given local date."""
    day = date.replace(hour=0, minute=0, second=0, microsecond=0)
    anchor, data = await _energy_data(dev, day, day + timedelta(days=1), 60)
    rows = []
    for i, wh in enumerate(data):
        ts = anchor + timedelta(hours=i)
        if day <= ts < day + timedelta(days=1):
            rows.append((ts.strftime("%Y-%m-%d %H:00"), int(wh)))
    return rows


def _quarter_start(d: datetime) -> datetime:
    return d.replace(month=(d.month - 1) // 3 * 3 + 1, day=1,
                     hour=0, minute=0, second=0, microsecond=0)


async def get_daily(dev: Device, start_date: datetime, end_date: datetime) -> list[tuple[str, int]]:
    """(date, wh) rows for start_date..end_date inclusive (local dates).

    Daily-interval requests MUST be quarter-aligned: the P110 returns the full
    quarter containing an aligned start (one slot per day) but silently returns
    quarter-anchored data for misaligned starts while echoing the requested
    start_timestamp — i.e. wrong dates. Verified on-device 2026-07-12.
    """
    start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    q = _quarter_start(start)
    while q <= end:
        next_q = _quarter_start(q + timedelta(days=93))
        anchor, data = await _energy_data(dev, q, next_q, 1440)
        if anchor != q:
            raise RuntimeError(f"daily anchor mismatch: requested {q}, got {anchor}")
        for i, wh in enumerate(data):
            d = q + timedelta(days=i)
            if start <= d <= end:
                rows.append((d.strftime("%Y-%m-%d"), int(wh)))
        q = next_q
    return rows


def device_info(dev: Device) -> dict:
    return {
        "alias": dev.alias,
        "model": dev.model,
        "mac": dev.mac,
        "ip": dev.host,
        "fw": getattr(dev, "hw_info", {}).get("sw_ver", ""),
        "is_on": dev.is_on,
        "rssi": getattr(dev, "rssi", None),
    }

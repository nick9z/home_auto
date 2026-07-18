"""Read Tapo T310 temp/humidity sensors through the H100 hub.

The T310 sensors have no IP address of their own — they report over a sub-GHz
mesh to the H100 hub, which we reach over the LAN. Two things differ from the
P110 plugs in tapo_client.py:

  1. We find the hub by MODEL ("H100"), not by a nickname, because there is
     only ever one hub.
  2. We must NOT call Device.update() on the hub. update() runs a big
     multi-request that reliably times out on the child-device query, which is
     exactly why earlier plug-style scans never "saw" the hub. Instead we
     connect and issue ONE raw get_child_device_list query, which returns every
     paired sensor's latest reading in a single response.

Same KASA_USERNAME / KASA_PASSWORD credentials from ~/.env as the plugs.
"""

import asyncio
import base64

from kasa import Discover

import tapo_client  # reuse _credentials(), _arp_ips(), timeouts

HUB_MODEL = "H100"
# Sensor categories we log readings for (temp + humidity). Buttons, contact
# sensors etc. are paired to the same hub but carry no daily reading.
TEMP_HUMIDITY_CATEGORY = "temp-hmdt-sensor"
NO_READING = -1000  # hub's sentinel for "no value"


async def _connect(ip: str):
    """discover_single WITHOUT update() — returns a connected Device or None."""
    try:
        return await Discover.discover_single(
            ip, timeout=tapo_client.PROBE_TIMEOUT, **tapo_client._credentials()
        )
    except Exception:
        return None


async def find_hub(cached_ip: str | None, lan: dict):
    """Return a connected H100 hub Device, or None.

    Tries the last-known hub IP first (fast, almost always right), then falls
    back to a concurrent probe of ARP neighbours + the whole subnet. Caller is
    responsible for hub.disconnect().
    """
    if cached_ip:
        hub = await _connect(cached_ip)
        if hub is not None and hub.model == HUB_MODEL:
            return hub
        if hub is not None:
            await hub.disconnect()

    tried = {cached_ip}
    arp = tapo_client._arp_ips(lan["iface"], lan["subnet"])
    sweep = [f"{lan['subnet']}.{i}" for i in range(1, 255)]
    candidates = [ip for ip in arp + sweep if ip not in tried]

    sem = asyncio.Semaphore(tapo_client.SWEEP_CONCURRENCY)

    async def guarded(ip):
        async with sem:
            return await _connect(ip)

    found = None
    for dev in await asyncio.gather(*(guarded(ip) for ip in candidates)):
        if dev is None:
            continue
        if found is None and dev.model == HUB_MODEL:
            found = dev
        else:
            await dev.disconnect()
    return found


def _name(child: dict) -> str:
    raw = child.get("nickname")
    if raw:
        try:
            return base64.b64decode(raw).decode()
        except Exception:
            pass
    return child["device_id"]


async def read_sensors(hub) -> list[dict]:
    """One raw query -> list of temp/humidity sensor readings.

    Offline sensors return stale temp/humidity from the hub, so we store those
    as None (online=False) and let summaries ignore them.
    """
    resp = await hub.protocol.query("get_child_device_list")
    children = resp["get_child_device_list"]["child_device_list"]

    sensors = []
    for c in children:
        if TEMP_HUMIDITY_CATEGORY not in c.get("category", ""):
            continue
        online = c.get("status") == "online"
        temp = c.get("current_temp")
        humidity = c.get("current_humidity")
        valid = online and temp != NO_READING and humidity != NO_READING
        sensors.append(
            {
                "sensor_id": c["device_id"],
                "name": _name(c),
                "model": c.get("model"),
                "online": online,
                "temp_c": temp if valid else None,
                "humidity": humidity if valid else None,
                "battery_low": bool(c.get("at_low_battery")),
                "rssi": c.get("rssi") if online else None,
            }
        )
    return sensors


def hub_info(hub) -> dict:
    return {
        "model": hub.model,
        "mac": hub.mac,
        "ip": hub.host,
        "fw": getattr(hub, "hw_info", {}).get("sw_ver", ""),
    }

"""Snapshot Tapo T310 temp/humidity readings into SQLite.

Run by cron every 30 minutes. Each run connects to the H100 hub, reads the
current temperature/humidity of every paired T310, and stores one timestamped
row per sensor. The morning summary and dashboard then compute daily
min/max/avg from these snapshots.

Unlike energy (which is cumulative and can be back-filled from the plug),
temp/humidity is an instantaneous value, so we sample it regularly instead of
pulling history once a night.

Usage: uv run python sensor_collector.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import db
import sensor_client

log = logging.getLogger("sensor_collector")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).resolve().parent / "sensor_collector.log"),
    ],
)


async def main() -> int:
    cfg = db.load_config()
    conn = db.connect(cfg)

    hub = await sensor_client.find_hub(db.cached_hub_ip(conn), cfg["lan"])
    if hub is None:
        log.error("H100 hub unreachable — no readings taken this run")
        conn.close()
        return 1

    try:
        info = sensor_client.hub_info(hub)
        # Store the hub in the devices table so cached_hub_ip finds it next run.
        db.upsert_device(conn, "Smart Hub H100", info["model"], info["mac"],
                         info["ip"], info["fw"])
        sensors = await sensor_client.read_sensors(hub)
    except Exception:
        log.exception("failed to read sensors from hub")
        conn.close()
        return 1
    finally:
        await hub.disconnect()

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    for s in sensors:
        db.upsert_sensor(conn, s["sensor_id"], s["name"], s["model"])
        db.insert_sensor_reading(conn, s["sensor_id"], ts, s["temp_c"],
                                 s["humidity"], s["battery_low"], s["online"])
        if s["online"]:
            log.info("%s: %.1f°C  %d%%RH%s", s["name"], s["temp_c"], s["humidity"],
                     "  LOW BATTERY" if s["battery_low"] else "")
        else:
            log.info("%s: offline (no reading)", s["name"])

    conn.commit()
    conn.close()
    if not sensors:
        log.warning("hub reachable but no temp/humidity sensors paired")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

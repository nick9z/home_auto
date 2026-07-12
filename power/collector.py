"""Nightly collector: pull hourly + daily energy from the plugs into SQLite.

Run by cron shortly after midnight. Idempotent — safe to re-run. On catch-up
after downtime it backfills daily totals up to `backfill_days` (60) and hourly
detail up to `hourly_backfill_days` (7, the device's hourly retention).

Usage: uv run python collector.py [--seed]   (--seed is just an alias; the
gap-driven backfill makes first run and catch-up the same code path)
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import db
import tapo_client

log = logging.getLogger("collector")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).resolve().parent / "collector.log"),
    ],
)


def missing_daily_dates(conn, alias: str, window_days: int) -> list[str]:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    have = {
        r["date"]
        for r in conn.execute("SELECT date FROM daily_energy WHERE alias=?", (alias,))
    }
    return [
        d.strftime("%Y-%m-%d")
        for i in range(window_days, 0, -1)
        if (d := today - timedelta(days=i)).strftime("%Y-%m-%d") not in have
    ]


def incomplete_hourly_dates(conn, alias: str, window_days: int) -> list[datetime]:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    counts = dict(
        conn.execute(
            """
            SELECT substr(hour_ts, 1, 10), count(*) FROM hourly_energy
            WHERE alias=? GROUP BY 1
            """,
            (alias,),
        ).fetchall()
    )
    return [
        d
        for i in range(window_days, 0, -1)
        if counts.get((d := today - timedelta(days=i)).strftime("%Y-%m-%d"), 0) < 24
    ]


async def collect_device(conn, dev, cfg) -> None:
    info = tapo_client.device_info(dev)
    db.upsert_device(conn, info["alias"], info["model"], info["mac"], info["ip"], info["fw"])
    alias = info["alias"]

    daily_missing = missing_daily_dates(conn, alias, cfg["backfill_days"])
    if daily_missing:
        start = datetime.strptime(daily_missing[0], "%Y-%m-%d")
        end = datetime.now() - timedelta(days=1)
        rows = await tapo_client.get_daily(dev, start, end)
        db.upsert_daily(conn, alias, rows)
        log.info("%s: daily %s..%s (%d rows, %d were missing)",
                 alias, daily_missing[0], end.strftime("%Y-%m-%d"), len(rows), len(daily_missing))
    else:
        log.info("%s: daily up to date", alias)

    hourly_days = incomplete_hourly_dates(conn, alias, cfg["hourly_backfill_days"])
    for day in hourly_days:
        rows = await tapo_client.get_hourly(dev, day)
        db.upsert_hourly(conn, alias, rows)
        log.info("%s: hourly %s (%d rows)", alias, day.strftime("%Y-%m-%d"), len(rows))
    conn.commit()


async def main() -> int:
    cfg = db.load_config()
    conn = db.connect(cfg)
    devices = await tapo_client.find_devices(cfg["devices"], db.cached_ips(conn), cfg["lan"])

    failures = 0
    for alias in cfg["devices"]:
        dev = devices.get(alias)
        if dev is None:
            log.error("%s: unreachable — will backfill on next run", alias)
            failures += 1
            continue
        try:
            await collect_device(conn, dev, cfg)
        except Exception:
            log.exception("%s: collection failed", alias)
            failures += 1
        finally:
            await dev.disconnect()

    conn.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""SQLite storage for Tapo power monitoring."""

import sqlite3
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    with open(BASE_DIR / "config.yaml") as f:
        return yaml.safe_load(f)


def connect(cfg: dict | None = None) -> sqlite3.Connection:
    cfg = cfg or load_config()
    conn = sqlite3.connect(BASE_DIR / cfg["db_path"])
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS devices (
            alias      TEXT PRIMARY KEY,
            model      TEXT,
            mac        TEXT,
            last_ip    TEXT,
            fw         TEXT,
            first_seen TEXT,
            last_seen  TEXT
        );
        CREATE TABLE IF NOT EXISTS hourly_energy (
            alias   TEXT NOT NULL,
            hour_ts TEXT NOT NULL,   -- local time "YYYY-MM-DD HH:00"
            wh      INTEGER NOT NULL,
            PRIMARY KEY (alias, hour_ts)
        );
        CREATE TABLE IF NOT EXISTS daily_energy (
            alias TEXT NOT NULL,
            date  TEXT NOT NULL,     -- local date "YYYY-MM-DD"
            wh    INTEGER NOT NULL,
            PRIMARY KEY (alias, date)
        );
        CREATE TABLE IF NOT EXISTS sensors (
            sensor_id  TEXT PRIMARY KEY,   -- hub child device_id
            name       TEXT,
            model      TEXT,
            first_seen TEXT,
            last_seen  TEXT
        );
        CREATE TABLE IF NOT EXISTS sensor_readings (
            sensor_id   TEXT NOT NULL,
            ts          TEXT NOT NULL,     -- local time "YYYY-MM-DD HH:MM"
            temp_c      REAL,              -- NULL when the sensor was offline
            humidity    INTEGER,           -- NULL when the sensor was offline
            battery_low INTEGER,           -- 0 / 1
            online      INTEGER,           -- 0 / 1
            PRIMARY KEY (sensor_id, ts)
        );
        """
    )
    return conn


def upsert_device(conn, alias, model, mac, ip, fw):
    conn.execute(
        """
        INSERT INTO devices (alias, model, mac, last_ip, fw, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
        ON CONFLICT(alias) DO UPDATE SET
            model=excluded.model, mac=excluded.mac, last_ip=excluded.last_ip,
            fw=excluded.fw, last_seen=excluded.last_seen
        """,
        (alias, model, mac, ip, fw),
    )


def upsert_hourly(conn, alias, rows):
    """rows: iterable of (hour_ts, wh)."""
    conn.executemany(
        """
        INSERT INTO hourly_energy (alias, hour_ts, wh) VALUES (?, ?, ?)
        ON CONFLICT(alias, hour_ts) DO UPDATE SET wh=excluded.wh
        """,
        [(alias, ts, wh) for ts, wh in rows],
    )


def upsert_daily(conn, alias, rows):
    """rows: iterable of (date, wh)."""
    conn.executemany(
        """
        INSERT INTO daily_energy (alias, date, wh) VALUES (?, ?, ?)
        ON CONFLICT(alias, date) DO UPDATE SET wh=excluded.wh
        """,
        [(alias, d, wh) for d, wh in rows],
    )


def cached_ips(conn) -> dict:
    return {r["alias"]: r["last_ip"] for r in conn.execute("SELECT alias, last_ip FROM devices")}


def tapo_aliases(cfg: dict) -> list[str]:
    """cfg['devices'] entries that are Tapo plugs, not Shelly."""
    shelly = set(cfg.get("shelly") or {})
    return [a for a in cfg["devices"] if a not in shelly]


def shelly_wanted(cfg: dict) -> dict[str, str]:
    """{alias: mac} for every configured Shelly."""
    return {alias: spec["mac"] for alias, spec in (cfg.get("shelly") or {}).items()}


def cached_hub_ip(conn) -> str | None:
    """Last-known IP of the H100 hub, stored in the devices table like a plug."""
    row = conn.execute(
        "SELECT last_ip FROM devices WHERE model=? LIMIT 1", ("H100",)
    ).fetchone()
    return row["last_ip"] if row else None


# ---------- sensors (T310 temp/humidity via the hub) ----------

def upsert_sensor(conn, sensor_id, name, model):
    conn.execute(
        """
        INSERT INTO sensors (sensor_id, name, model, first_seen, last_seen)
        VALUES (?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
        ON CONFLICT(sensor_id) DO UPDATE SET
            name=excluded.name, model=excluded.model, last_seen=excluded.last_seen
        """,
        (sensor_id, name, model),
    )


def insert_sensor_reading(conn, sensor_id, ts, temp_c, humidity, battery_low, online):
    conn.execute(
        """
        INSERT INTO sensor_readings (sensor_id, ts, temp_c, humidity, battery_low, online)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(sensor_id, ts) DO UPDATE SET
            temp_c=excluded.temp_c, humidity=excluded.humidity,
            battery_low=excluded.battery_low, online=excluded.online
        """,
        (sensor_id, ts, temp_c, humidity, int(battery_low), int(online)),
    )


def latest_sensor_readings(conn):
    """Most recent reading per sensor, joined with its name/model."""
    return conn.execute(
        """
        SELECT s.sensor_id, s.name, s.model,
               r.ts, r.temp_c, r.humidity, r.battery_low, r.online
        FROM sensors s
        LEFT JOIN sensor_readings r ON r.sensor_id = s.sensor_id
             AND r.ts = (SELECT MAX(ts) FROM sensor_readings x WHERE x.sensor_id = s.sensor_id)
        ORDER BY s.name
        """
    ).fetchall()


def sensor_daily_stats(conn, date: str):
    """Per-sensor min/max/avg temp + humidity for one local date.

    Only rows with a real reading (temp_c NOT NULL, i.e. the sensor was online)
    are counted; n is how many samples that was.
    """
    return conn.execute(
        """
        SELECT s.sensor_id, s.name,
               MIN(r.temp_c)  AS tmin, MAX(r.temp_c)  AS tmax, AVG(r.temp_c)  AS tavg,
               MIN(r.humidity) AS hmin, MAX(r.humidity) AS hmax, AVG(r.humidity) AS havg,
               COUNT(r.temp_c) AS n
        FROM sensors s
        LEFT JOIN sensor_readings r ON r.sensor_id = s.sensor_id
             AND substr(r.ts, 1, 10) = ? AND r.temp_c IS NOT NULL
        GROUP BY s.sensor_id, s.name
        ORDER BY s.name
        """,
        (date,),
    ).fetchall()


def sensor_history(conn, date: str):
    """All readings for one local date, for charting (oldest first)."""
    return conn.execute(
        """
        SELECT sensor_id, ts, temp_c, humidity FROM sensor_readings
        WHERE substr(ts, 1, 10) = ? ORDER BY ts
        """,
        (date,),
    ).fetchall()


def daily_range(conn, start: str, end: str):
    """Per-device daily Wh for start <= date <= end (local dates)."""
    return conn.execute(
        """
        SELECT alias, date, wh FROM daily_energy
        WHERE date BETWEEN ? AND ? ORDER BY date, alias
        """,
        (start, end),
    ).fetchall()


def hourly_for_date(conn, date: str):
    return conn.execute(
        """
        SELECT alias, hour_ts, wh FROM hourly_energy
        WHERE hour_ts LIKE ? || ' %' ORDER BY hour_ts, alias
        """,
        (date,),
    ).fetchall()

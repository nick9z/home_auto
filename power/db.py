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

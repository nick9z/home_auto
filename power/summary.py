"""Morning power summary: yesterday + week-to-date vs last week, pushed to phone.

Run by cron at 07:30. Reads only SQLite (no device access), so it works even
if a plug is offline. Weeks start Monday.

Usage: uv run python summary.py [--dry-run]   (--dry-run prints instead of sending)
"""

import json
import sys
import urllib.request
from datetime import date, timedelta

import db
import tapo_client


def _fmt_kwh(wh: int, tariff: float, currency: str) -> str:
    kwh = wh / 1000
    return f"{kwh:.1f} kWh (${kwh * tariff:.2f})"


def _total(conn, start: date, end: date) -> int:
    if start > end:
        return 0
    row = conn.execute(
        "SELECT COALESCE(SUM(wh),0) FROM daily_energy WHERE date BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return row[0]


def build_summary(conn, cfg: dict, today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    tariff, cur = cfg["tariff_per_kwh"], cfg["currency"]

    per_device = conn.execute(
        "SELECT alias, wh FROM daily_energy WHERE date=? ORDER BY wh DESC",
        (yesterday.isoformat(),),
    ).fetchall()
    y_total = sum(r["wh"] for r in per_device)

    # Week-to-date: Monday of yesterday's week, through yesterday.
    week_start = yesterday - timedelta(days=yesterday.weekday())
    wtd = _total(conn, week_start, yesterday)
    prev_week = _total(conn, week_start - timedelta(days=7), week_start - timedelta(days=1))

    title = f"Power — {yesterday.strftime('%a %d %b')}: {_fmt_kwh(y_total, tariff, cur)}"
    lines = []
    if per_device:
        lines.append(" · ".join(f"{r['alias']} {r['wh']/1000:.1f} kWh" for r in per_device))
    else:
        lines.append("No data collected for yesterday — check collector.log")
    wtd_line = f"Week to date: {_fmt_kwh(wtd, tariff, cur)}"
    if prev_week:
        pct = (wtd - prev_week) / prev_week * 100
        wtd_line += f" — last week: {_fmt_kwh(prev_week, tariff, cur)} ({pct:+.0f}%)"
    lines.append(wtd_line)

    sensor_lines = build_sensor_lines(conn, yesterday)
    if sensor_lines:
        lines.append("")  # blank separator
        lines.extend(sensor_lines)
    return title, "\n".join(lines)


def build_sensor_lines(conn, yesterday: date) -> list[str]:
    """Temp/humidity lines for the morning push: current reading + yesterday's
    range per sensor, plus offline / low-battery warnings."""
    latest = db.latest_sensor_readings(conn)
    if not latest:
        return []
    stats = {r["sensor_id"]: r for r in db.sensor_daily_stats(conn, yesterday.isoformat())}

    lines = []
    for r in latest:
        if r["online"] and r["temp_c"] is not None:
            line = f"{r['name']}: now {r['temp_c']:.1f}°C {r['humidity']}%RH"
            s = stats.get(r["sensor_id"])
            if s and s["n"]:
                line += f" · yest {s['tmin']:.0f}–{s['tmax']:.0f}°C"
            if r["battery_low"]:
                line = "🔋 " + line + " — LOW BATTERY"
            else:
                line = "🌡 " + line
        else:
            line = f"⚠ {r['name']}: offline"
        lines.append(line)
    return lines


def send_push(cfg: dict, title: str, body: str) -> dict:
    api_key = tapo_client.read_env(cfg["phone"]["api_key_env"])[cfg["phone"]["api_key_env"]]
    req = urllib.request.Request(
        cfg["phone"]["url"] + "/api/notify",
        method="POST",
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        data=json.dumps({"title": title, "body": body}).encode(),
    )
    return json.load(urllib.request.urlopen(req, timeout=40))


def main() -> int:
    cfg = db.load_config()
    conn = db.connect(cfg)
    title, body = build_summary(conn, cfg)
    conn.close()
    if "--dry-run" in sys.argv:
        print(title)
        print(body)
        return 0
    result = send_push(cfg, title, body)
    print(f"sent: {result}")
    return 0 if result.get("pushed_devices", 0) >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())

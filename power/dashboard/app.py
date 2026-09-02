"""LAN dashboard for home power monitoring (Tapo plugs + Shelly meters).

Run: uv run uvicorn dashboard.app:app --host 0.0.0.0 --port 8090
Serves device status (live, queried on demand) and usage charts from SQLite.
"""

import asyncio
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import shelly_client  # noqa: E402
import tapo_client  # noqa: E402

app = FastAPI(title="Home Power")
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

LIVE_CACHE_TTL = 20
_live_cache: dict = {"ts": 0.0, "data": None, "lock": asyncio.Lock()}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    cfg = db.load_config()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "devices": cfg["devices"],
            "tariff": cfg["tariff_per_kwh"],
            "currency": cfg["currency"],
        },
    )


@app.get("/api/summary")
async def api_summary():
    cfg = db.load_config()
    conn = db.connect(cfg)
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    prev_start = week_start - timedelta(days=7)

    def total(start: date, end: date) -> int:
        if start > end:
            return 0
        return conn.execute(
            "SELECT COALESCE(SUM(wh),0) FROM daily_energy WHERE date BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()[0]

    out = {
        "yesterday_wh": total(yesterday, yesterday),
        "wtd_wh": total(week_start, yesterday),
        "prev_week_wh": total(prev_start, week_start - timedelta(days=1)),
        "week_start": week_start.isoformat(),
        "tariff": cfg["tariff_per_kwh"],
    }
    conn.close()
    return out


@app.get("/api/daily")
async def api_daily(days: int = 30):
    cfg = db.load_config()
    conn = db.connect(cfg)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=min(days, cfg["backfill_days"]) - 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    series = {alias: dict.fromkeys(dates, 0) for alias in cfg["devices"]}
    for r in db.daily_range(conn, start.isoformat(), end.isoformat()):
        if r["alias"] in series:
            series[r["alias"]][r["date"]] = r["wh"]
    conn.close()
    return {"dates": dates, "series": {a: list(v.values()) for a, v in series.items()}}


@app.get("/api/hourly")
async def api_hourly(day: str = ""):
    cfg = db.load_config()
    conn = db.connect(cfg)
    day = day or (date.today() - timedelta(days=1)).isoformat()
    hours = [f"{day} {h:02d}:00" for h in range(24)]
    series = {alias: dict.fromkeys(hours, 0) for alias in cfg["devices"]}
    for r in db.hourly_for_date(conn, day):
        if r["alias"] in series:
            series[r["alias"]][r["hour_ts"]] = r["wh"]
    # Earliest date with hourly data, for the date picker's lower bound.
    first = conn.execute("SELECT MIN(substr(hour_ts,1,10)) FROM hourly_energy").fetchone()[0]
    conn.close()
    return {
        "day": day,
        "hours": list(range(24)),
        "series": {a: list(v.values()) for a, v in series.items()},
        "min_day": first,
    }


@app.get("/api/sensors")
async def api_sensors():
    """Latest stored temp/humidity per sensor + today's range (from SQLite).

    Served from the DB, not a live hub query, so the page loads fast and never
    blocks on the hub. The collector refreshes these every 30 minutes.
    """
    cfg = db.load_config()
    conn = db.connect(cfg)
    today = date.today().isoformat()
    stats = {r["sensor_id"]: r for r in db.sensor_daily_stats(conn, today)}
    out = []
    for r in db.latest_sensor_readings(conn):
        s = stats.get(r["sensor_id"])
        out.append({
            "name": r["name"],
            "model": r["model"],
            "online": bool(r["online"]),
            "temp_c": r["temp_c"],
            "humidity": r["humidity"],
            "battery_low": bool(r["battery_low"]),
            "ts": r["ts"],
            "today_tmin": s["tmin"] if s and s["n"] else None,
            "today_tmax": s["tmax"] if s and s["n"] else None,
        })
    conn.close()
    return {"sensors": out}


@app.get("/api/sensor_history")
async def api_sensor_history(day: str = ""):
    """Per-sensor temp/humidity samples for one local day, for the trend chart.

    Each point carries minutes-since-midnight (t) so the chart can place it on a
    fixed 0..1440 x-axis regardless of how many samples exist. Offline samples
    (temp NULL) are dropped so lines only span times the sensor was reporting.
    """
    cfg = db.load_config()
    conn = db.connect(cfg)
    day = day or date.today().isoformat()
    names = {r["sensor_id"]: r["name"] for r in db.latest_sensor_readings(conn)}
    series: dict[str, list] = {}
    for r in db.sensor_history(conn, day):
        if r["temp_c"] is None:
            continue
        name = names.get(r["sensor_id"], r["sensor_id"])
        minutes = int(r["ts"][11:13]) * 60 + int(r["ts"][14:16])
        series.setdefault(name, []).append(
            {"t": minutes, "temp_c": r["temp_c"], "humidity": r["humidity"]}
        )
    first = conn.execute("SELECT MIN(substr(ts,1,10)) FROM sensor_readings").fetchone()[0]
    conn.close()
    return {"day": day, "series": series, "min_day": first}


@app.get("/api/live")
async def api_live():
    async with _live_cache["lock"]:
        if _live_cache["data"] and time.time() - _live_cache["ts"] < LIVE_CACHE_TTL:
            return _live_cache["data"]
        cfg = db.load_config()
        conn = db.connect(cfg)
        cached = db.cached_ips(conn)
        last_collected = {
            r["alias"]: r["last_seen"]
            for r in conn.execute("SELECT alias, last_seen FROM devices")
        }
        tapo_wanted = db.tapo_aliases(cfg)
        shelly_map = db.shelly_wanted(cfg)
        tapo_devs, shelly_devs = await asyncio.gather(
            tapo_client.find_devices(tapo_wanted, cached, cfg["lan"]),
            asyncio.to_thread(shelly_client.find_devices, shelly_map, cached, cfg["lan"]),
        )
        out = []
        for alias in cfg["devices"]:
            entry = {"alias": alias, "reachable": False,
                     "last_collected": last_collected.get(alias)}
            if alias in shelly_map:
                rec = shelly_devs.get(alias)
                if rec is not None:
                    try:
                        info = shelly_client.device_info(rec)
                        live = await asyncio.to_thread(shelly_client.get_live, rec["ip"])
                        db.upsert_device(conn, alias, info["model"], info["mac"],
                                         info["ip"], info["fw"])
                        entry["reachable"] = True
                        entry.update(info)
                        entry.update(live)
                        month_start = date.today().replace(day=1).isoformat()
                        prior = conn.execute(
                            """SELECT COALESCE(SUM(wh),0) FROM daily_energy
                               WHERE alias=? AND date>=? AND date<?""",
                            (alias, month_start, date.today().isoformat()),
                        ).fetchone()[0]
                        entry["month_wh"] = prior + (entry.get("today_wh") or 0)
                    except Exception:
                        entry["reachable"] = False
            else:
                dev = tapo_devs.get(alias)
                if dev is not None:
                    try:
                        info = tapo_client.device_info(dev)
                        live = await tapo_client.get_live(dev)
                        db.upsert_device(conn, alias, info["model"], info["mac"],
                                         info["ip"], info["fw"])
                        entry["reachable"] = True
                        entry.update(info)
                        entry.update(live)
                    except Exception:
                        entry["reachable"] = False
                    finally:
                        await dev.disconnect()
            out.append(entry)
        conn.commit()
        conn.close()
        data = {"devices": out, "ts": datetime.now().strftime("%H:%M:%S")}
        _live_cache.update(ts=time.time(), data=data)
        return data

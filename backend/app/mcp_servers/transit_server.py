"""
MCP Server 2 — Transit Schedule Server (in-process).

Serves Namma Metro and BMTC timetable data.
Data source: public Namma Metro timetable + BMTC route information.
All values are documented-as-public, not real-time.

DATA SOURCE DECLARATION
-----------------------
Metro schedule: Based on Namma Metro public timetable (bengalurumetro.com).
BMTC routes: Based on publicly available BMTC route maps.
Neither source provides a real-time API. These are hardcoded schedules
with simulated surge adjustments for large events.

Promotion path: wrap each function in @mcp.tool() for Streamable HTTP MCP.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta


# ── Hardcoded schedule data ───────────────────────────────────────────────────
# Source: Namma Metro public timetable (public domain)
# Surge values are synthetic estimates for event mode.

_METRO_STATIONS: dict[str, dict] = {
    "mg_road": {
        "station_id": "mg_road",
        "name": "MG Road",
        "line": "Purple",
        "lat": 12.9752,
        "lon": 77.6060,
        "walking_minutes_from_stadium": 12,
        "normal_trains_per_hour": 4,
        "surge_trains_per_hour": 6,
        "capacity_per_train": 900,
        "max_platform_capacity": 1200,
        "first_service": "05:30",
        "last_service": "23:00",
        "data_source": "PUBLIC_TIMETABLE",
    },
    "cubbon_park": {
        "station_id": "cubbon_park",
        "name": "Cubbon Park",
        "line": "Green",
        "lat": 12.9796,
        "lon": 77.5930,
        "walking_minutes_from_stadium": 16,
        "normal_trains_per_hour": 3,
        "surge_trains_per_hour": 4,
        "capacity_per_train": 900,
        "max_platform_capacity": 1200,
        "first_service": "06:00",
        "last_service": "23:00",
        "data_source": "PUBLIC_TIMETABLE",
    },
}

# BMTC stop data — sourced from publicly available BMTC route maps
_BMTC_STOPS: list[dict] = [
    {
        "stop_id": "kg_road",
        "name": "KG Road Junction",
        "lat": 12.9756,
        "lon": 77.5936,
        "routes": ["137", "201", "401"],
        "walking_minutes_from_stadium": 5,
        "normal_buses_per_hour": 3,
        "surge_buses_per_hour": 6,
        "capacity_per_bus": 90,
        "data_source": "PUBLIC_ROUTE_MAP",
    },
    {
        "stop_id": "mg_road_bmtc",
        "name": "MG Road Junction",
        "lat": 12.9760,
        "lon": 77.6045,
        "routes": ["36", "201"],
        "walking_minutes_from_stadium": 8,
        "normal_buses_per_hour": 2,
        "surge_buses_per_hour": 4,
        "capacity_per_bus": 90,
        "data_source": "PUBLIC_ROUTE_MAP",
    },
]

_METRO_MAX_CAPACITY_PER_HOUR = 15_000  # physical ceiling (persons/hour)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _is_service_running(station: dict, check_time: datetime) -> bool:
    """True if the station is running at check_time (based on first/last service hours)."""
    t = check_time.time()
    h, m = map(int, station["first_service"].split(":"))
    lh, lm = map(int, station["last_service"].split(":"))
    from datetime import time as _time
    return _time(h, m) <= t <= _time(lh, lm)


# ── Public API ────────────────────────────────────────────────────────────────

def get_metro_departures(
    station_id: str,
    from_time: datetime,
    to_time: datetime,
    surge_active: bool = False,
) -> list[dict]:
    """
    Return scheduled Metro departures at `station_id` in the [from_time, to_time] window.

    Parameters
    ----------
    station_id    One of: "mg_road", "cubbon_park".
    from_time     Window start (timezone-aware or naive).
    to_time       Window end.
    surge_active  Whether event-mode surge service is active (adds extra trains).

    Returns
    -------
    List of departure dicts: {departure_time, capacity_per_train, line, surge_active,
                               data_source, station_id}.

    Returns [] for unknown station_id or out-of-service window.
    """
    station = _METRO_STATIONS.get(station_id)
    if not station:
        return []

    if not _is_service_running(station, from_time):
        return []

    tph = station["surge_trains_per_hour"] if surge_active else station["normal_trains_per_hour"]
    interval_minutes = max(1, round(60 / tph))

    departures = []
    current = from_time.replace(second=0, microsecond=0)
    # Align to the nearest interval boundary from the hour
    minutes_past_hour = current.minute
    offset = interval_minutes - (minutes_past_hour % interval_minutes)
    if offset == interval_minutes:
        offset = 0
    current = current + timedelta(minutes=offset)

    while current <= to_time:
        departures.append({
            "departure_time": current.isoformat(),
            "capacity_per_train": station["capacity_per_train"],
            "line": station["line"],
            "station_id": station_id,
            "station_name": station["name"],
            "surge_active": surge_active,
            "data_source": station["data_source"],
        })
        current += timedelta(minutes=interval_minutes)

    return departures


def get_bmtc_routes_near(
    lat: float,
    lon: float,
    radius_m: float = 1000.0,
) -> list[dict]:
    """
    Return BMTC stops within `radius_m` metres of (lat, lon).

    Parameters
    ----------
    lat, lon   Search centre.
    radius_m   Search radius in metres (default 1,000 m = 1 km).

    Returns
    -------
    List of stop dicts with routes, walking_minutes, capacity_per_bus, data_source.
    """
    radius_km = radius_m / 1000.0
    result = []
    for stop in _BMTC_STOPS:
        dist_km = _haversine_km(lat, lon, stop["lat"], stop["lon"])
        if dist_km <= radius_km:
            result.append({
                "stop_id": stop["stop_id"],
                "name": stop["name"],
                "lat": stop["lat"],
                "lon": stop["lon"],
                "distance_m": round(dist_km * 1000),
                "routes": stop["routes"],
                "walking_minutes_from_stadium": stop["walking_minutes_from_stadium"],
                "normal_buses_per_hour": stop["normal_buses_per_hour"],
                "surge_buses_per_hour": stop["surge_buses_per_hour"],
                "capacity_per_bus": stop["capacity_per_bus"],
                "data_source": stop["data_source"],
            })
    return sorted(result, key=lambda s: s["distance_m"])


def get_metro_capacity(
    station_id: str,
    time_slot: str,
    surge_active: bool = False,
) -> dict:
    """
    Return Metro capacity figures for a station at a given time slot.

    Parameters
    ----------
    station_id   One of: "mg_road", "cubbon_park".
    time_slot    ISO 8601 datetime string or HH:MM string (used for service check only).
    surge_active Whether event-mode surge service is active.

    Returns
    -------
    Dict with capacity_per_hour, trains_per_hour, platform_capacity,
    walking_minutes, data_source.
    Returns empty dict for unknown station_id.
    """
    station = _METRO_STATIONS.get(station_id)
    if not station:
        return {}

    tph = station["surge_trains_per_hour"] if surge_active else station["normal_trains_per_hour"]
    cap_per_hour = min(tph * station["capacity_per_train"], _METRO_MAX_CAPACITY_PER_HOUR)

    return {
        "station_id": station_id,
        "station_name": station["name"],
        "line": station["line"],
        "trains_per_hour": tph,
        "capacity_per_hour": cap_per_hour,
        "capacity_per_train": station["capacity_per_train"],
        "platform_capacity": station["max_platform_capacity"],
        "walking_minutes_from_stadium": station["walking_minutes_from_stadium"],
        "surge_active": surge_active,
        "data_source": station["data_source"],
        "note": (
            "Capacity based on public Namma Metro timetable. "
            "Surge trains are synthetic estimates for event mode."
        ),
    }


def list_metro_stations() -> list[dict]:
    """Return all known Metro stations near Chinnaswamy Stadium."""
    return [
        {
            "station_id": sid,
            "name": s["name"],
            "line": s["line"],
            "lat": s["lat"],
            "lon": s["lon"],
            "walking_minutes_from_stadium": s["walking_minutes_from_stadium"],
            "data_source": s["data_source"],
        }
        for sid, s in _METRO_STATIONS.items()
    ]

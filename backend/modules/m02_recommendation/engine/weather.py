"""Weather for a city and a day, from Open-Meteo (free, no API key). Cached 30 min; safe fallback offline."""

from __future__ import annotations

import datetime as dt
import time

import httpx

from shared.config import settings

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_TTL = 30 * 60
DAILY = "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max"

# WMO weather codes -> short condition
_CODES = [
    ((0,), "clear"),
    ((1, 2), "partly cloudy"),
    ((3,), "cloudy"),
    ((45, 48), "fog"),
    ((51, 53, 55, 56, 57), "drizzle"),
    ((61, 63, 65, 66, 67, 80, 81, 82), "rain"),
    ((71, 73, 75, 77, 85, 86), "snow"),
    ((95, 96, 99), "storm"),
]


def condition(code: int) -> str:
    return next((name for codes, name in _CODES if code in codes), "cloudy")


def is_rainy(cond: str) -> bool:
    return cond in ("drizzle", "rain", "storm", "snow")


def get_weather(city: str, day: dt.date | None = None) -> tuple[dict, str]:
    """Returns ({temp_c, condition}, source) where source is "open-meteo" or "fallback"."""
    day = day or dt.date.today()
    key = (city.lower(), day.isoformat())
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1], "open-meteo"
    try:
        with httpx.Client(timeout=4) as c:
            geo = c.get(GEOCODE_URL, params={"name": city, "count": 1}).json()["results"][0]
            fc = c.get(
                settings.weather_api_url,
                params={
                    "latitude": geo["latitude"],
                    "longitude": geo["longitude"],
                    "timezone": "auto",
                    "daily": DAILY,
                    "start_date": day.isoformat(),
                    "end_date": day.isoformat(),
                },
            ).json()["daily"]
        # Daytime feel: weighted toward the max, which is when people are out.
        temp = 0.65 * fc["temperature_2m_max"][0] + 0.35 * fc["temperature_2m_min"][0]
        cond = condition(int(fc["weather_code"][0]))
        rain_prob = (fc.get("precipitation_probability_max") or [None])[0] or 0
        if rain_prob >= 60:
            cond = cond if is_rainy(cond) else "rain"
        out = {"temp_c": round(temp, 1), "condition": cond}
        _cache[key] = (time.time(), out)
        return out, "open-meteo"
    except Exception:  # offline, unknown city, API change: never block a recommendation on the weather
        return {"temp_c": 20.0, "condition": "clear"}, "fallback"

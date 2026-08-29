"""Open-Meteo API client for Fixture Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    OPEN_METEO_URL,
    PRECIPITATION_FORECAST_PERIODS,
)
from .geocoder import Location


HOURLY_VARIABLES = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation_probability",
        "precipitation",
        "weather_code",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "wind_gusts_10m",
        "is_day",
    ]
)

DAILY_VARIABLES = ",".join(
    [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "precipitation_sum",
        "precipitation_probability_max",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "sunrise",
        "sunset",
    ]
)

CURRENT_VARIABLES = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "precipitation_probability",
        "weather_code",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "wind_gusts_10m",
        "is_day",
    ]
)

MINUTELY_15_VARIABLES = ",".join(
    [
        "precipitation",
        "rain",
        "showers",
        "snowfall",
        "weather_code",
    ]
)


class OpenMeteoClient:
    """Small Open-Meteo client."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the client."""
        self.session = async_get_clientsession(hass)

    async def async_get_forecasts(
        self,
        locations: list[Location],
        timezone: str,
    ) -> list[dict[str, Any]]:
        """Get forecasts for multiple locations."""
        if not locations:
            return []

        latitude = ",".join(
            str(location.latitude)
            for location in locations
        )
        longitude = ",".join(
            str(location.longitude)
            for location in locations
        )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "forecast_days": 14,
            "forecast_minutely_15": (
                PRECIPITATION_FORECAST_PERIODS
            ),
            "hourly": HOURLY_VARIABLES,
            "daily": DAILY_VARIABLES,
            "current": CURRENT_VARIABLES,
            "minutely_15": MINUTELY_15_VARIABLES,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }

        async with self.session.get(
            OPEN_METEO_URL,
            params=params,
            timeout=30,
        ) as response:
            response.raise_for_status()
            data = await response.json()

        # Open-Meteo returns a dict for one location and a list
        # for multiple locations.
        if isinstance(data, list):
            return data

        return [data]
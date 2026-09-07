"""Tests for the Fixture Weather entity."""

import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.components.weather import WeatherEntityFeature

from custom_components.fixture_weather.weather import FixtureWeatherEntity


def _run_async(coroutine):
    """Run a coroutine without changing the process event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def test_weather_entity_exposes_forecast_location_coordinates() -> None:
    """Weather attributes should expose the selected forecast coordinates."""

    class StubCoordinator:
        base_location_name = "Base City"
        data = SimpleNamespace(
            current_location="Boston, MA",
            current_location_lat=42.3601,
            current_location_lon=-71.0589,
            days_until_event_start=0,
            current={
                "precipitation_probability": 40,
                "precipitation": 0.5,
            },
        )

        def async_add_listener(self, *_args, **_kwargs):
            return lambda: None

    class StubEntry:
        entry_id = "abc123"
        title = "Test entries"

    entity = FixtureWeatherEntity(StubCoordinator(), StubEntry())

    assert entity.extra_state_attributes["forecast_location_lat"] == 42.3601
    assert entity.extra_state_attributes["forecast_location_lon"] == -71.0589


def test_weather_entity_exposes_twice_daily_forecast() -> None:
    """Twice-daily forecasts contain daytime and nighttime periods."""

    class StubCoordinator:
        base_location_name = "Base City"
        hass = SimpleNamespace(
            config=SimpleNamespace(time_zone="UTC")
        )
        data = SimpleNamespace(
            current_location="Base City",
            current_location_lat=42.3601,
            current_location_lon=-71.0589,
            days_until_event_start=0,
            current={},
            daily=[
                {
                    "sunrise": "2026-08-29T05:55",
                    "sunset": "2026-08-29T19:25",
                    "weather_code": 0,
                    "temperature_2m_max": 24.0,
                    "temperature_2m_min": 15.0,
                    "apparent_temperature_max": 24.5,
                    "apparent_temperature_min": 14.5,
                    "wind_speed_10m_max": 18.0,
                    "wind_gusts_10m_max": 28.0,
                }
            ],
        )

        def async_add_listener(self, *_args, **_kwargs):
            return lambda: None

    class StubEntry:
        entry_id = "abc123"
        title = "Test entries"

    entity = FixtureWeatherEntity(StubCoordinator(), StubEntry())

    assert (
        entity.supported_features
        & WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    forecasts = _run_async(
        entity.async_forecast_twice_daily()
    )

    assert forecasts == [
        {
            "datetime": "2026-08-29T05:55:00+00:00",
            "is_daytime": True,
            "condition": "sunny",
            "native_temperature": 24.0,
            "native_apparent_temperature": 24.5,
            "native_wind_speed": 18.0,
            "native_wind_gust_speed": 28.0,
        },
        {
            "datetime": "2026-08-29T19:25:00+00:00",
            "is_daytime": False,
            "condition": "clear-night",
            "native_temperature": 15.0,
            "native_apparent_temperature": 14.5,
            "native_wind_speed": 18.0,
            "native_wind_gust_speed": 28.0,
        },
    ]


def test_weather_entity_defaults_missing_twice_daily_timestamps() -> None:
    """Missing sunrise and sunset values use stable local-time defaults."""

    class StubCoordinator:
        base_location_name = "Base City"
        hass = SimpleNamespace(
            config=SimpleNamespace(time_zone="UTC")
        )
        data = SimpleNamespace(
            current_location="Base City",
            current_location_lat=42.3601,
            current_location_lon=-71.0589,
            days_until_event_start=0,
            current={},
            daily=[
                {
                    "local_date": date(2026, 8, 29),
                    "sunrise": None,
                    "sunset": "not-a-timestamp",
                    "weather_code": 1,
                }
            ],
        )

        def async_add_listener(self, *_args, **_kwargs):
            return lambda: None

    class StubEntry:
        entry_id = "abc123"
        title = "Test entries"

    entity = FixtureWeatherEntity(StubCoordinator(), StubEntry())

    forecasts = _run_async(
        entity.async_forecast_twice_daily()
    )

    assert [forecast["datetime"] for forecast in forecasts] == [
        "2026-08-29T06:00:00+00:00",
        "2026-08-29T18:00:00+00:00",
    ]


def test_weather_entity_exposes_hourly_is_daytime() -> None:
    """Hourly forecasts expose the source day/night value."""

    class StubCoordinator:
        base_location_name = "Base City"
        data = SimpleNamespace(
            current_location="Base City",
            current_location_lat=42.3601,
            current_location_lon=-71.0589,
            days_until_event_start=0,
            current={},
            hourly=[
                {
                    "datetime": "2026-08-29T16:00:00+00:00",
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T16:00:00+00:00"
                    ),
                    "weather_code": 0,
                    "is_day": 1,
                },
                {
                    "datetime": "2026-08-29T17:00:00+00:00",
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T17:00:00+00:00"
                    ),
                    "weather_code": 0,
                    "is_day": 0,
                },
                {
                    "datetime": "2026-08-29T18:00:00+00:00",
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T18:00:00+00:00"
                    ),
                    "weather_code": 0,
                    "is_day": None,
                },
            ],
        )

        def async_add_listener(self, *_args, **_kwargs):
            return lambda: None

    class StubEntry:
        entry_id = "abc123"
        title = "Test entries"

    entity = FixtureWeatherEntity(StubCoordinator(), StubEntry())
    now = datetime.fromisoformat("2026-08-29T16:15:00+00:00")

    with patch(
        "custom_components.fixture_weather.weather.dt_util.now",
        return_value=now,
    ):
        forecasts = _run_async(entity.async_forecast_hourly())

    assert [
        forecast["is_daytime"] for forecast in forecasts
    ] == [True, False, None]

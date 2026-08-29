"""Tests for the Fixture Weather coordinator."""

from datetime import date, datetime
from types import SimpleNamespace

from custom_components.fixture_weather.coordinator import (
    FixtureWeatherCoordinator,
)
from custom_components.fixture_weather.geocoder import Location



def test_apply_event_location_assigns_event_days_only() -> None:
    """An event uses its location through, but not including, its end date."""
    locations: dict[date, str] = {}

    FixtureWeatherCoordinator._apply_event_location(
        {
            "location": "Boston, MA",
            "start": "2026-08-30T10:00:00+00:00",
            "end": "2026-09-01T00:00:00+00:00",
        },
        locations,
        date(2026, 8, 29),
    )

    assert locations == {
        date(2026, 8, 30): "Boston, MA",
        date(2026, 8, 31): "Boston, MA",
    }



def test_apply_event_location_preserves_first_event_for_day() -> None:
    """The first calendar event returned wins when events overlap a day."""
    locations: dict[date, str] = {}
    event = {
        "location": "Boston, MA",
        "start": "2026-08-30T10:00:00+00:00",
        "end": "2026-08-30T12:00:00+00:00",
    }

    FixtureWeatherCoordinator._apply_event_location(
        event,
        locations,
        date(2026, 8, 29),
    )
    FixtureWeatherCoordinator._apply_event_location(
        {
            **event,
            "location": "London, UK",
        },
        locations,
        date(2026, 8, 29),
    )

    assert locations == {date(2026, 8, 30): "Boston, MA"}



def test_precipitation_summary_stops_at_gap() -> None:
    """A later precipitation period does not extend an earlier period."""
    now = datetime.fromisoformat("2026-08-29T12:05:00+00:00")
    summary, attributes = (
        FixtureWeatherCoordinator._build_precipitation_summary(
            [
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T12:00:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T12:15:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T12:15:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T12:30:00+00:00"
                    ),
                    "precipitation": 0,
                    "rain": 0,
                    "snowfall": 0,
                    "weather_code": 0,
                },
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T20:00:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T20:15:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
            ],
            now,
            "Boston, MA",
        )
    )

    assert summary == "Rain until 12:15pm"
    assert attributes["start"] == "2026-08-29T12:00:00+00:00"
    assert attributes["end"] == "2026-08-29T12:15:00+00:00"
    assert attributes["amount"] == 0.2


def test_merge_hourly_forecast_starts_at_current_hour() -> None:
    """The current hour should be included even after the minute mark."""
    coordinator = object.__new__(FixtureWeatherCoordinator)
    coordinator.hass = SimpleNamespace(
        config=SimpleNamespace(time_zone="UTC")
    )
    coordinator.base_location_name = "Boston, MA"

    now = datetime.fromisoformat("2026-08-29T17:15:00+00:00")

    result = coordinator._merge_hourly_forecast(
        {
            date(2026, 8, 29): "Boston, MA",
        },
        {
            "Boston, MA": Location(
                query="Boston, MA",
                latitude=42.3601,
                longitude=-71.0589,
                display_name="Boston, MA",
            )
        },
        {
            (42.3601, -71.0589): {
                "hourly": {
                    "time": [
                        "2026-08-29T17:00",
                        "2026-08-29T18:00",
                    ],
                    "temperature_2m": [18.2, 19.0],
                    "weather_code": [0, 1],
                    "is_day": [1, 1],
                }
            }
        },
        now,
    )

    assert [entry["local_datetime"] for entry in result] == [
        datetime.fromisoformat("2026-08-29T17:00:00+00:00"),
        datetime.fromisoformat("2026-08-29T18:00:00+00:00"),
    ]

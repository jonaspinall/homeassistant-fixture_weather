"""Tests for the Fixture Weather coordinator."""

from datetime import date, datetime

from custom_components.fixture_weather.coordinator import (
    FixtureWeatherCoordinator,
)



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

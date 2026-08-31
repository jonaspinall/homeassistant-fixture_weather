"""Tests for the Fixture Weather coordinator."""

from datetime import date, datetime
from types import SimpleNamespace

from custom_components.fixture_weather.coordinator import (
    FixtureWeatherCoordinator,
)
from custom_components.fixture_weather.geocoder import Location
from custom_components.fixture_weather.weather import FixtureWeatherEntity



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


def test_precipitation_summary_stops_at_next_event_end() -> None:
    """Only precipitation within the next event window is considered."""
    now = datetime.fromisoformat("2026-08-29T17:05:00+00:00")
    summary, attributes = (
        FixtureWeatherCoordinator._build_precipitation_summary(
            [
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T17:45:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T18:00:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T18:00:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T18:15:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T19:00:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T19:15:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
            ],
            now,
            "Boston, MA",
            event_start=datetime.fromisoformat(
                "2026-08-29T18:00:00+00:00"
            ),
            event_end=datetime.fromisoformat(
                "2026-08-29T19:00:00+00:00"
            ),
        )
    )

    assert summary == "Rain from 6:00pm to 6:15pm"
    assert attributes["start"] == "2026-08-29T18:00:00+00:00"
    assert attributes["end"] == "2026-08-29T18:15:00+00:00"


def test_precipitation_summary_keeps_active_period_past_event_end() -> None:
    """A precipitation block that is already active can continue through its end."""
    now = datetime.fromisoformat("2026-08-29T15:50:00+00:00")
    summary, attributes = (
        FixtureWeatherCoordinator._build_precipitation_summary(
            [
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T15:45:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T16:00:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T16:00:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T16:15:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
                {
                    "period_start": datetime.fromisoformat(
                        "2026-08-29T17:00:00+00:00"
                    ),
                    "local_datetime": datetime.fromisoformat(
                        "2026-08-29T17:15:00+00:00"
                    ),
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "snowfall": 0,
                    "weather_code": 61,
                },
            ],
            now,
            "Boston, MA",
            event_start=datetime.fromisoformat(
                "2026-08-29T15:00:00+00:00"
            ),
            event_end=datetime.fromisoformat(
                "2026-08-29T16:00:00+00:00"
            ),
        )
    )

    assert summary == "Rain until 4:15pm"
    assert attributes["start"] == "2026-08-29T15:45:00+00:00"
    assert attributes["end"] == "2026-08-29T16:15:00+00:00"


def test_days_until_event_start_is_zero_for_active_or_near_event() -> None:
    """Active or soon-to-start events count as zero days remaining."""
    now = datetime.fromisoformat("2026-08-29T11:00:00+00:00")

    assert (
        FixtureWeatherCoordinator._days_until_event_start(
            [
                {
                    "location": "Boston, MA",
                    "start": "2026-08-29T12:00:00+00:00",
                    "end": "2026-08-29T13:00:00+00:00",
                }
            ],
            now,
        )
        == 0
    )

    assert (
        FixtureWeatherCoordinator._days_until_event_start(
            [
                {
                    "location": "Boston, MA",
                    "start": "2026-08-30T12:00:00+00:00",
                    "end": "2026-08-30T13:00:00+00:00",
                }
            ],
            now,
        )
        == 1
    )


def test_days_until_event_start_counts_full_days() -> None:
    """The value counts full 24-hour periods until the next event."""
    now = datetime.fromisoformat("2026-08-29T11:00:00+00:00")

    assert (
        FixtureWeatherCoordinator._days_until_event_start(
            [
                {
                    "location": "Boston, MA",
                    "start": "2026-08-31T12:00:00+00:00",
                    "end": "2026-08-31T13:00:00+00:00",
                }
            ],
            now,
        )
        == 2
    )

    assert (
        FixtureWeatherCoordinator._days_until_event_start(
            [
                {
                    "location": "Boston, MA",
                    "start": "2026-09-02T12:00:00+00:00",
                    "end": "2026-09-02T13:00:00+00:00",
                }
            ],
            now,
        )
        == 4
    )


def test_days_until_event_start_is_negative_when_no_future_event_exists() -> None:
    """Without a future event, the attribute should not appear as zero."""
    now = datetime.fromisoformat("2026-08-29T11:00:00+00:00")

    assert FixtureWeatherCoordinator._days_until_event_start([], now) == -1

    assert (
        FixtureWeatherCoordinator._days_until_event_start(
            [
                {
                    "location": "Boston, MA",
                    "start": "2026-08-28T09:00:00+00:00",
                    "end": "2026-08-28T10:00:00+00:00",
                }
            ],
            now,
        )
        == -1
    )


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


def test_get_current_location_uses_base_location_without_calendar() -> None:
    """Without a calendar, the base location remains active."""
    now = datetime.fromisoformat("2026-08-29T12:30:00+00:00")

    location = FixtureWeatherCoordinator._get_current_location_name(
        [],
        now,
        "Base City",
        datetime.fromisoformat("2026-09-12T00:00:00+00:00"),
    )

    assert location == "Base City"


def test_get_current_location_uses_upcoming_event_before_it_starts() -> None:
    """The first upcoming event should win even before it starts."""
    now = datetime.fromisoformat("2026-08-29T23:50:00+00:00")

    location = FixtureWeatherCoordinator._get_current_location_name(
        [
            {
                "location": "Boston, MA",
                "start": "2026-08-29T20:00:00+00:00",
                "end": "2026-08-29T21:30:00+00:00",
            },
            {
                "location": "New York, NY",
                "start": "2026-08-30T00:15:00+00:00",
                "end": "2026-08-30T02:00:00+00:00",
            },
        ],
        now,
        "Base City",
        datetime.fromisoformat("2026-09-12T00:00:00+00:00"),
    )

    assert location == "New York, NY"


def test_precipitation_summary_without_calendar_uses_full_forecast() -> None:
    """Without events, precipitation is not capped to a calendar window."""
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

    assert summary == "Rain until 12:30pm"
    assert attributes["start"] == "2026-08-29T12:00:00+00:00"
    assert attributes["end"] == "2026-08-29T12:30:00+00:00"
    assert attributes["amount"] == 0.4


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


def test_get_current_location_uses_upcoming_event_before_it_starts() -> None:
    """An upcoming calendar event should replace the previous venue before its start."""
    now = datetime.fromisoformat("2026-08-29T23:50:00+00:00")

    location = FixtureWeatherCoordinator._get_current_location_name(
        [
            {
                "location": "Boston, MA",
                "start": "2026-08-29T20:00:00+00:00",
                "end": "2026-08-29T21:30:00+00:00",
            },
            {
                "location": "New York, NY",
                "start": "2026-08-30T00:15:00+00:00",
                "end": "2026-08-30T02:00:00+00:00",
            },
        ],
        now,
        "Base City",
        datetime.fromisoformat("2026-09-12T00:00:00+00:00"),
    )

    assert location == "New York, NY"


def test_get_current_location_uses_next_event_at_start() -> None:
    """The next event wins from its start time, cutting short the grace period."""
    now = datetime.fromisoformat("2026-08-30T00:15:00+00:00")

    location = FixtureWeatherCoordinator._get_current_location_name(
        [
            {
                "location": "Boston, MA",
                "start": "2026-08-29T20:00:00+00:00",
                "end": "2026-08-29T21:30:00+00:00",
            },
            {
                "location": "New York, NY",
                "start": "2026-08-30T00:15:00+00:00",
                "end": "2026-08-30T02:00:00+00:00",
            },
        ],
        now,
        "Base City",
        datetime.fromisoformat("2026-09-12T00:00:00+00:00"),
    )

    assert location == "New York, NY"


def test_get_current_location_keeps_last_event_to_forecast_end() -> None:
    """A final event remains selected through the forecast window."""
    now = datetime.fromisoformat("2026-08-30T03:15:00+00:00")

    location = FixtureWeatherCoordinator._get_current_location_name(
        [
            {
                "location": "Boston, MA",
                "start": "2026-08-29T20:00:00+00:00",
                "end": "2026-08-29T21:30:00+00:00",
            },
            {
                "location": "New York, NY",
                "start": "2026-08-30T00:15:00+00:00",
                "end": "2026-08-30T02:00:00+00:00",
            },
        ],
        now,
        "Base City",
        datetime.fromisoformat("2026-09-12T00:00:00+00:00"),
    )

    assert location == "New York, NY"

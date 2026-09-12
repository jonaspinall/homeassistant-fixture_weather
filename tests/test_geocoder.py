"""Tests for Fixture Weather geocoding."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call

from custom_components.fixture_weather.geocoder import (
    Geocoder,
    Location,
)


def _run_async(coroutine):
    """Run a coroutine without changing the process event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def _create_geocoder() -> Geocoder:
    """Create a geocoder with mocked Home Assistant dependencies."""
    geocoder = Geocoder.__new__(Geocoder)
    geocoder.hass = MagicMock()
    geocoder.session = MagicMock()
    geocoder.store = MagicMock()
    geocoder._cache = {}
    return geocoder


def test_geocode_uses_full_location_when_available() -> None:
    """Use the complete location when it can be geocoded."""
    geocoder = _create_geocoder()

    location = Location(
        query="Edgbaston, Birmingham",
        latitude=52.4558,
        longitude=-1.9130,
        display_name="Edgbaston Stadium, Birmingham, England",
    )

    geocoder._async_geocode_nominatim = AsyncMock(
        return_value=location
    )
    geocoder.store.async_save = AsyncMock()

    result = _run_async(
        geocoder.async_geocode("Edgbaston, Birmingham")
    )

    assert result == location

    geocoder._async_geocode_nominatim.assert_awaited_once_with(
        "Edgbaston, Birmingham"
    )


def test_geocode_falls_back_through_location_parts() -> None:
    """Try venue, locality, and country when the full location fails."""
    geocoder = _create_geocoder()

    location = Location(
        query="Johannesburg",
        latitude=-26.2041,
        longitude=28.0473,
        display_name="Johannesburg, South Africa",
    )

    geocoder._async_geocode_nominatim = AsyncMock(
        side_effect=[
            None,
            None,
            location,
        ]
    )
    geocoder.store.async_save = AsyncMock()

    result = _run_async(
        geocoder.async_geocode(
            "The Wanderers Stadium, Johannesburg, South Africa"
        )
    )

    assert result == Location(
        query="The Wanderers Stadium, Johannesburg, South Africa",
        latitude=-26.2041,
        longitude=28.0473,
        display_name="Johannesburg, South Africa",
        timezone=None,
    )

    assert geocoder._async_geocode_nominatim.await_args_list == [
        call("The Wanderers Stadium, Johannesburg, South Africa"),
        call("The Wanderers Stadium"),
        call("Johannesburg"),
    ]

    assert geocoder.store.async_save.await_args_list == [
        call(geocoder._cache)
    ]

    assert geocoder._cache == {
        "the wanderers stadium, johannesburg, south africa": {
            "latitude": -26.2041,
            "longitude": 28.0473,
            "display_name": "Johannesburg, South Africa",
            "timezone": None,
        }
    }


def test_geocode_uses_cached_location() -> None:
    """Use the cached location without geocoding again."""
    geocoder = _create_geocoder()

    geocoder._cache = {
        "edgbaston, birmingham": {
            "latitude": 52.4558,
            "longitude": -1.9130,
            "display_name": "Edgbaston Stadium, Birmingham, England",
            "timezone": None,
        }
    }

    geocoder._async_geocode_nominatim = AsyncMock()

    result = _run_async(
        geocoder.async_geocode("Edgbaston, Birmingham")
    )

    assert result == Location(
        query="Edgbaston, Birmingham",
        latitude=52.4558,
        longitude=-1.9130,
        display_name="Edgbaston Stadium, Birmingham, England",
        timezone=None,
    )

    geocoder._async_geocode_nominatim.assert_not_awaited()
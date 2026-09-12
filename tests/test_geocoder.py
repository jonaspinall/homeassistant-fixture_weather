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
    geocoder._async_geocode_open_meteo = AsyncMock()
    geocoder.store.async_save = AsyncMock()

    result = _run_async(
        geocoder.async_geocode("Edgbaston, Birmingham")
    )

    assert result == location

    geocoder._async_geocode_nominatim.assert_awaited_once_with(
        "Edgbaston, Birmingham"
    )
    geocoder._async_geocode_open_meteo.assert_not_awaited()


def test_geocode_falls_back_to_venue_name() -> None:
    """Fall back to the venue name when the full location fails."""
    geocoder = _create_geocoder()

    location = Location(
        query="The Rose Bowl",
        latitude=50.9240,
        longitude=-1.3220,
        display_name="The Rose Bowl, West End, Hampshire, England",
    )

    geocoder._async_geocode_nominatim = AsyncMock(
        side_effect=[None, location]
    )
    geocoder._async_geocode_open_meteo = AsyncMock(
        return_value=None
    )
    geocoder.store.async_save = AsyncMock()

    result = _run_async(
        geocoder.async_geocode("The Rose Bowl, Southampton")
    )

    assert result == Location(
        query="The Rose Bowl, Southampton",
        latitude=50.9240,
        longitude=-1.3220,
        display_name="The Rose Bowl, West End, Hampshire, England",
        timezone=None,
    )

    assert geocoder._async_geocode_nominatim.await_args_list == [
        call("The Rose Bowl, Southampton"),
        call("The Rose Bowl"),
    ]

    assert geocoder._async_geocode_open_meteo.await_args_list == [
        call("The Rose Bowl, Southampton"),
    ]

    assert geocoder._cache == {
        "the rose bowl, southampton": {
            "latitude": 50.9240,
            "longitude": -1.3220,
            "display_name": "The Rose Bowl, West End, Hampshire, England",
            "timezone": None,
        }
    }

    geocoder.store.async_save.assert_awaited_once_with(
        geocoder._cache
    )


def test_geocode_falls_back_to_venue_with_open_meteo() -> None:
    """Use Open-Meteo for the venue-only fallback."""
    geocoder = _create_geocoder()

    location = Location(
        query="The Rose Bowl",
        latitude=50.9240,
        longitude=-1.3220,
        display_name="The Rose Bowl",
        timezone="Europe/London",
    )

    geocoder._async_geocode_nominatim = AsyncMock(
        side_effect=[None, None]
    )
    geocoder._async_geocode_open_meteo = AsyncMock(
        side_effect=[None, location]
    )
    geocoder.store.async_save = AsyncMock()

    result = _run_async(
        geocoder.async_geocode("The Rose Bowl, Southampton")
    )

    assert result == Location(
        query="The Rose Bowl, Southampton",
        latitude=50.9240,
        longitude=-1.3220,
        display_name="The Rose Bowl",
        timezone="Europe/London",
    )

    assert geocoder._async_geocode_nominatim.await_args_list == [
        call("The Rose Bowl, Southampton"),
        call("The Rose Bowl"),
    ]

    assert geocoder._async_geocode_open_meteo.await_args_list == [
        call("The Rose Bowl, Southampton"),
        call("The Rose Bowl"),
    ]
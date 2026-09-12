"""Geocoding support for Fixture Weather."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import (
    GEOCODE_CACHE_KEY,
    GEOCODE_CACHE_VERSION,
    NOMINATIM_URL,
    OPEN_METEO_GEOCODING_URL,
)

_LOGGER = logging.getLogger(__name__)

_NOMINATIM_USER_AGENT = "Home Assistant Fixture Weather/0.1.0"

_nominatim_lock = asyncio.Lock()
_last_nominatim_request = 0.0


@dataclass(frozen=True)
class Location:
    """A geocoded location."""

    query: str
    latitude: float
    longitude: float
    display_name: str
    timezone: str | None = None


class Geocoder:
    """Geocoder with persistent caching."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the geocoder."""
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.store = Store(
            hass,
            GEOCODE_CACHE_VERSION,
            GEOCODE_CACHE_KEY,
        )
        self._cache: dict[str, dict[str, Any]] | None = None

    async def _async_load_cache(self) -> None:
        """Load the persistent cache."""
        if self._cache is not None:
            return

        data = await self.store.async_load()

        if isinstance(data, dict):
            self._cache = data
        else:
            self._cache = {}

    async def async_geocode(self, query: str) -> Location:
        """Geocode a location, using the cache where possible."""
        await self._async_load_cache()

        cache_key = query.strip().casefold()

        assert self._cache is not None

        if cached := self._cache.get(cache_key):
            return Location(
                query=query,
                latitude=float(cached["latitude"]),
                longitude=float(cached["longitude"]),
                display_name=cached["display_name"],
                timezone=cached.get("timezone"),
            )

        # Try the complete location first. If it contains a venue and
        # locality (e.g. "The Rose Bowl, Southampton"), also try the
        # venue on its own if the complete query cannot be resolved.
        queries = [query]

        if "," in query:
            venue = query.split(",", 1)[0].strip()
            if venue and venue.casefold() != query.strip().casefold():
                queries.append(venue)

        for geocode_query in queries:
            location = await self._async_geocode_nominatim(geocode_query)

            if location is None:
                location = await self._async_geocode_open_meteo(geocode_query)

            if location is not None:
                # Cache against the original calendar location, even when
                # the fallback venue-only query was successful.
                self._cache[cache_key] = {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "display_name": location.display_name,
                    "timezone": location.timezone,
                }

                await self.store.async_save(self._cache)

                return Location(
                    query=query,
                    latitude=location.latitude,
                    longitude=location.longitude,
                    display_name=location.display_name,
                    timezone=location.timezone,
                )

        raise ValueError(f"Could not geocode location: {query}")

    async def _async_geocode_nominatim(
        self,
        query: str,
    ) -> Location | None:
        """Try Nominatim."""
        global _last_nominatim_request

        async with _nominatim_lock:
            elapsed = time.monotonic() - _last_nominatim_request

            if elapsed < 1.1:
                await asyncio.sleep(1.1 - elapsed)

            try:
                async with self.session.get(
                    NOMINATIM_URL,
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "limit": 1,
                        "layer": "poi,manmade,address",
                    },
                    headers={
                        "User-Agent": _NOMINATIM_USER_AGENT,
                    },
                    timeout=15,
                ) as response:
                    _last_nominatim_request = time.monotonic()

                    response.raise_for_status()
                    results = await response.json()

            except Exception as err:
                _LOGGER.debug(
                    "Nominatim geocoding failed for %s: %s",
                    query,
                    err,
                )
                return None

        if not results:
            return None

        result = results[0]

        try:
            return Location(
                query=query,
                latitude=float(result["lat"]),
                longitude=float(result["lon"]),
                display_name=result.get("display_name", query),
            )
        except (KeyError, TypeError, ValueError):
            return None

    async def _async_geocode_open_meteo(
        self,
        query: str,
    ) -> Location | None:
        """Try the Open-Meteo geocoder."""
        try:
            async with self.session.get(
                OPEN_METEO_GEOCODING_URL,
                params={
                    "name": query,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                },
                timeout=15,
            ) as response:
                response.raise_for_status()
                data = await response.json()

        except Exception as err:
            _LOGGER.debug(
                "Open-Meteo geocoding failed for %s: %s",
                query,
                err,
            )
            return None

        results = data.get("results") or []

        if not results:
            return None

        result = results[0]

        try:
            return Location(
                query=query,
                latitude=float(result["latitude"]),
                longitude=float(result["longitude"]),
                display_name=result.get("name", query),
                timezone=result.get("timezone"),
            )
        except (KeyError, TypeError, ValueError):
            return None

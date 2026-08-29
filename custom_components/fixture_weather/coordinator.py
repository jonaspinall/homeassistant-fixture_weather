"""Data coordinator for Fixture Weather."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BASE_LOCATION,
    CONF_CALENDAR,
    DEFAULT_UPDATE_INTERVAL,
    EVENT_LOCATION_GRACE_PERIOD,
    FORECAST_DAYS,
    MINUTELY_PRECIPITATION_THRESHOLD,
)
from .geocoder import Geocoder, Location
from .open_meteo import OpenMeteoClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class FixtureWeatherData:
    """Data made available to the entities."""

    hourly: list[dict[str, Any]]
    daily: list[dict[str, Any]]
    minutely_precipitation: list[dict[str, Any]]
    current: dict[str, Any]
    current_location: str
    locations_by_date: dict[date, str]
    precipitation_summary: str
    precipitation_attributes: dict[str, Any]


class FixtureWeatherCoordinator(
    DataUpdateCoordinator[FixtureWeatherData]
):
    """Coordinate calendar, geocoding and weather data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.base_location_name = entry.data[CONF_BASE_LOCATION]
        self.calendar_entity = entry.data.get(CONF_CALENDAR)

        self.geocoder = Geocoder(hass)
        self.open_meteo = OpenMeteoClient(hass)

        self._base_location: Location | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"fixture_weather_{entry.entry_id}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> FixtureWeatherData:
        """Fetch and assemble all weather data."""
        try:
            return await self._async_build_data()
        except Exception as err:
            raise UpdateFailed(
                f"Unable to update Fixture Weather: {err}"
            ) from err

    async def _async_build_data(self) -> FixtureWeatherData:
        """Build the combined weather data."""
        now = dt_util.now()
        local_today = now.date()

        end = dt_util.start_of_local_day(
            now + timedelta(days=FORECAST_DAYS)
        )

        if self._base_location is None:
            self._base_location = await self.geocoder.async_geocode(
                self.base_location_name
            )

        # Start with no calendar-specific locations.
        #
        # We keep this separate from locations_by_date so that the
        # base location can genuinely be a fallback. Otherwise we
        # wouldn't be able to distinguish "no event today" from
        # "an event exists today but its location happens to be
        # the base location".
        event_locations_by_date: dict[date, str] = {}
        events: list[dict[str, Any]] = []

        if self.calendar_entity:
            events = await self._async_get_calendar_events(
                dt_util.start_of_local_day(now),
                end,
            )

            for event in events:
                self._apply_event_location(
                    event,
                    event_locations_by_date,
                    local_today,
                )

        # Default every day to the configured base location, then
        # overwrite days for which the calendar supplies a location.
        locations_by_date: dict[date, str] = {}

        for offset in range(FORECAST_DAYS):
            day = local_today + timedelta(days=offset)
            locations_by_date[day] = (
                event_locations_by_date.get(
                    day,
                    self.base_location_name,
                )
            )

        # Collect all unique locations needed for this forecast.
        location_names = set(locations_by_date.values())

        locations: dict[str, Location] = {
            self.base_location_name: self._base_location
        }

        for location_name in location_names:
            if location_name in locations:
                continue

            try:
                locations[location_name] = (
                    await self.geocoder.async_geocode(location_name)
                )
            except ValueError as err:
                _LOGGER.warning(
                    "Could not geocode calendar location %s; "
                    "using base location instead: %s",
                    location_name,
                    err,
                )

                # If a venue can't be geocoded, use the base location
                # for every day that was assigned to that venue.
                for day, assigned_location in list(
                    locations_by_date.items()
                ):
                    if assigned_location == location_name:
                        locations_by_date[day] = (
                            self.base_location_name
                        )

        # Remove duplicate coordinates. Two differently named calendar
        # locations may resolve to the same point.
        unique_locations = list(
            {
                (
                    location.latitude,
                    location.longitude,
                ): location
                for location in locations.values()
            }.values()
        )

        forecasts = await self.open_meteo.async_get_forecasts(
            unique_locations,
            self.hass.config.time_zone,
        )

        forecast_by_location: dict[
            tuple[float, float],
            dict[str, Any],
        ] = {}

        for location, forecast in zip(unique_locations, forecasts):
            forecast_by_location[
                (
                    location.latitude,
                    location.longitude,
                )
            ] = forecast

        hourly = self._merge_hourly_forecast(
            locations_by_date,
            locations,
            forecast_by_location,
            now,
        )

        minutely_precipitation = (
            self._merge_minutely_precipitation(
                locations_by_date,
                locations,
                forecast_by_location,
                now,
            )
        )

        daily = self._merge_daily_forecast(
            locations_by_date,
            locations,
            forecast_by_location,
        )

        current_location_name = self._get_current_location_name(
            events,
            now,
            self.base_location_name,
            end,
        )

        current_location = locations.get(
            current_location_name,
            self._base_location,
        )

        assert current_location is not None

        current_forecast = forecast_by_location[
            (
                current_location.latitude,
                current_location.longitude,
            )
        ]

        current = current_forecast.get(
            "current",
            {},
        )

        summary, attributes = self._build_precipitation_summary(
            minutely_precipitation,
            now,
            current_location_name,
        )

        return FixtureWeatherData(
            hourly=hourly,
            daily=daily,
            minutely_precipitation=minutely_precipitation,
            current=current,
            current_location=current_location_name,
            locations_by_date=locations_by_date,
            precipitation_summary=summary,
            precipitation_attributes=attributes,
        )

    async def _async_get_calendar_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Get events from the configured calendar."""
        response = await self.hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": self.calendar_entity,
                "start_date_time": start,
                "end_date_time": end,
            },
            blocking=True,
            return_response=True,
        )

        calendar_data = response.get(
            self.calendar_entity,
            {},
        )

        return calendar_data.get(
            "events",
            [],
        )

    @staticmethod
    def _get_current_location_name(
        events: list[dict[str, Any]],
        now: datetime,
        base_location_name: str,
        forecast_end: datetime | None = None,
    ) -> str:
        """Return the current event location, including the grace period."""
        current_event: tuple[str, datetime, datetime] | None = None
        next_event: tuple[str, datetime, datetime] | None = None
        last_event: tuple[str, datetime, datetime] | None = None

        for event in sorted(
            events,
            key=lambda event: (
                _parse_calendar_datetime(event.get("start"))
                or datetime.max.replace(tzinfo=dt_util.UTC),
            ),
        ):
            location = event.get("location")

            if not location:
                continue

            location = location.strip()

            if not location:
                continue

            start = _parse_calendar_datetime(
                event.get("start")
            )

            end = _parse_calendar_datetime(
                event.get("end")
            )

            if start is None:
                continue

            if end is None:
                end = start

            last_event = (location, start, end)

            if start <= now:
                current_event = (location, start, end)
                continue

            if next_event is None:
                next_event = (location, start, end)

        if current_event is not None:
            location, _, end = current_event

            if now < end:
                return location

            if now < end + EVENT_LOCATION_GRACE_PERIOD:
                if next_event is not None and next_event[1] <= now:
                    return next_event[0]
                return location

            if (
                next_event is not None
                and next_event[1] <= now
            ):
                return next_event[0]

            if (
                last_event is not None
                and current_event == last_event
                and forecast_end is not None
                and now < forecast_end
            ):
                return location

            return base_location_name

        if next_event is not None:
            return next_event[0]

        if (
            last_event is not None
            and forecast_end is not None
            and now < forecast_end
        ):
            return last_event[0]

        return base_location_name

    @staticmethod
    def _apply_event_location(
        event: dict[str, Any],
        event_locations_by_date: dict[date, str],
        local_today: date,
    ) -> None:
        """Apply an event location to its calendar day(s)."""
        location = event.get("location")

        if not location:
            return

        location = location.strip()

        if not location:
            return

        start = _parse_calendar_datetime(
            event.get("start")
        )

        end = _parse_calendar_datetime(
            event.get("end")
        )

        if start is None:
            return

        start_date = start.date()
        end_date = start_date

        if end is not None and end > start:
            # Treat the event end as exclusive. This prevents an event
            # ending exactly at midnight from assigning its location
            # to the following day.
            end_inclusive = end - timedelta(
                microseconds=1
            )
            end_date = end_inclusive.date()

        current = max(
            start_date,
            local_today,
        )

        while current <= end_date:
            # If two events have different locations on the same day,
            # the first event returned by the calendar wins.
            #
            # This is intentional for sports calendars, where a team
            # would not normally have two fixtures at different venues
            # on the same day.
            event_locations_by_date.setdefault(
                current,
                location,
            )

            current += timedelta(days=1)

    def _merge_hourly_forecast(
        self,
        locations_by_date: dict[date, str],
        locations: dict[str, Location],
        forecast_by_location: dict[
            tuple[float, float],
            dict[str, Any],
        ],
        now: datetime,
    ) -> list[dict[str, Any]]:
        """Merge hourly forecasts according to calendar locations."""
        result: list[dict[str, Any]] = []

        # Build lookup tables keyed by local datetime.
        lookups: dict[
            str,
            dict[datetime, dict[str, Any]],
        ] = {}

        for name, location in locations.items():
            forecast = forecast_by_location[
                (
                    location.latitude,
                    location.longitude,
                )
            ]

            hourly_data = forecast.get(
                "hourly",
                {},
            )

            times = hourly_data.get(
                "time",
                [],
            )

            lookup: dict[
                datetime,
                dict[str, Any],
            ] = {}

            for index, timestamp in enumerate(times):
                local_dt = _parse_open_meteo_local_time(
                    timestamp,
                    self.hass.config.time_zone,
                )

                if local_dt is None:
                    continue

                lookup[local_dt] = {
                    key: values[index]
                    for key, values in hourly_data.items()
                    if key != "time"
                    and index < len(values)
                }

            lookups[name] = lookup

        all_times = sorted(
            {
                timestamp
                for lookup in lookups.values()
                for timestamp in lookup
            }
        )

        current_hour = now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        for local_dt in all_times:
            if local_dt < current_hour:
                continue

            location_name = locations_by_date.get(
                local_dt.date(),
                self.base_location_name,
            )

            weather = lookups.get(
                location_name,
                {},
            ).get(local_dt)

            if weather is None:
                weather = lookups[
                    self.base_location_name
                ].get(local_dt)

            if weather is None:
                continue

            result.append(
                {
                    "datetime": local_dt.astimezone(
                        dt_util.UTC
                    ).isoformat(),
                    "local_datetime": local_dt,
                    **weather,
                }
            )

        return result

    def _merge_minutely_precipitation(
        self,
        locations_by_date: dict[date, str],
        locations: dict[str, Location],
        forecast_by_location: dict[
            tuple[float, float],
            dict[str, Any],
        ],
        now: datetime,
    ) -> list[dict[str, Any]]:
        """Merge 15-minute precipitation forecasts."""
        result: list[dict[str, Any]] = []

        lookups: dict[
            str,
            dict[datetime, dict[str, Any]],
        ] = {}

        for name, location in locations.items():
            forecast = forecast_by_location[
                (
                    location.latitude,
                    location.longitude,
                )
            ]

            minutely_data = forecast.get(
                "minutely_15",
                {},
            )

            times = minutely_data.get(
                "time",
                [],
            )

            lookup: dict[
                datetime,
                dict[str, Any],
            ] = {}

            for index, timestamp in enumerate(times):
                local_dt = _parse_open_meteo_local_time(
                    timestamp,
                    self.hass.config.time_zone,
                )

                if local_dt is None:
                    continue

                lookup[local_dt] = {
                    key: values[index]
                    for key, values in minutely_data.items()
                    if key != "time"
                    and index < len(values)
                }

            lookups[name] = lookup

        all_times = sorted(
            {
                timestamp
                for lookup in lookups.values()
                for timestamp in lookup
            }
        )

        for local_dt in all_times:
            if local_dt <= now:
                continue

            location_name = locations_by_date.get(
                local_dt.date(),
                self.base_location_name,
            )

            weather = lookups.get(
                location_name,
                {},
            ).get(local_dt)

            if weather is None:
                weather = lookups[
                    self.base_location_name
                ].get(local_dt)

            if weather is None:
                continue

            # Open-Meteo's 15-minute precipitation values represent
            # precipitation accumulated during the preceding 15 minutes.
            period_start = local_dt - timedelta(
                minutes=15
            )

            result.append(
                {
                    "datetime": local_dt.astimezone(
                        dt_util.UTC
                    ).isoformat(),
                    "local_datetime": local_dt,
                    "period_start": period_start,
                    **weather,
                }
            )

        return result

    def _merge_daily_forecast(
        self,
        locations_by_date: dict[date, str],
        locations: dict[str, Location],
        forecast_by_location: dict[
            tuple[float, float],
            dict[str, Any],
        ],
    ) -> list[dict[str, Any]]:
        """Merge daily forecasts according to calendar locations."""
        result: list[dict[str, Any]] = []

        lookups: dict[
            str,
            dict[date, dict[str, Any]],
        ] = {}

        for name, location in locations.items():
            forecast = forecast_by_location[
                (
                    location.latitude,
                    location.longitude,
                )
            ]

            daily_data = forecast.get(
                "daily",
                {},
            )

            times = daily_data.get(
                "time",
                [],
            )

            lookup: dict[
                date,
                dict[str, Any],
            ] = {}

            for index, timestamp in enumerate(times):
                try:
                    day = date.fromisoformat(timestamp)
                except (TypeError, ValueError):
                    continue

                lookup[day] = {
                    key: values[index]
                    for key, values in daily_data.items()
                    if key != "time"
                    and index < len(values)
                }

            lookups[name] = lookup

        for day in sorted(locations_by_date):
            location_name = locations_by_date[day]

            weather = lookups.get(
                location_name,
                {},
            ).get(day)

            if weather is None:
                weather = lookups[
                    self.base_location_name
                ].get(day)

            if weather is None:
                continue

            timezone = dt_util.get_time_zone(
                self.hass.config.time_zone
            )

            assert timezone is not None

            local_midnight = datetime.combine(
                day,
                datetime.min.time(),
                tzinfo=timezone,
            )

            result.append(
                {
                    "datetime": local_midnight.astimezone(
                        dt_util.UTC
                    ).isoformat(),
                    "local_date": day,
                    **weather,
                }
            )

        return result

    @staticmethod
    def _build_precipitation_summary(
        minutely: list[dict[str, Any]],
        now: datetime,
        current_location: str,
    ) -> tuple[
        str,
        dict[str, Any],
    ]:
        """Build a precipitation summary from 15-minute data."""

        periods: list[
            tuple[
                datetime,
                datetime,
                str,
                float,
            ]
        ] = []

        for entry in minutely:
            period_end = entry.get(
                "local_datetime"
            )

            period_start = entry.get(
                "period_start"
            )

            if not isinstance(
                period_start,
                datetime,
            ) or not isinstance(
                period_end,
                datetime,
            ):
                continue

            precipitation = float(
                entry.get(
                    "precipitation",
                    0,
                )
                or 0
            )

            rain = float(
                entry.get(
                    "rain",
                    0,
                )
                or 0
            )

            snowfall = float(
                entry.get(
                    "snowfall",
                    0,
                )
                or 0
            )

            weather_code = entry.get(
                "weather_code"
            )

            precipitation_type = _precipitation_type(
                rain,
                snowfall,
                weather_code,
            )

            # Treat any measurable 15-minute precipitation as
            # precipitation for the summary.
            if (
                precipitation
                < MINUTELY_PRECIPITATION_THRESHOLD
                and rain
                < MINUTELY_PRECIPITATION_THRESHOLD
                and snowfall
                < MINUTELY_PRECIPITATION_THRESHOLD
            ):
                continue

            # Ignore periods that have completely finished.
            if period_end <= now:
                continue

            periods.append(
                (
                    period_start,
                    period_end,
                    precipitation_type,
                    precipitation,
                )
            )

        if not periods:
            return (
                "No significant precipitation expected",
                {
                    "location": current_location,
                    "precipitation_type": None,
                    "start": None,
                    "end": None,
                    "amount": 0,
                },
            )

        periods.sort(
            key=lambda item: item[0]
        )

        first_start = periods[0][0]
        end = periods[0][1]

        types = {
            periods[0][2]
        }

        total_amount = periods[0][3]

        # Combine adjacent 15-minute precipitation periods.
        for (
            start,
            period_end,
            precip_type,
            amount,
        ) in periods[1:]:
            if start <= end:
                end = max(
                    end,
                    period_end,
                )
                types.add(
                    precip_type
                )
                total_amount += amount
            else:
                break

        precipitation_type = _combine_precipitation_types(
            types
        )

        def format_time(
            value: datetime,
        ) -> str:
            """Format a local time as 12-hour am/pm."""
            return (
                value.strftime("%I:%M%p")
                .lstrip("0")
                .lower()
            )

        # If the first precipitation period has already started,
        # describe the current situation rather than saying it
        # starts in the past.
        if first_start <= now < end:
            summary = (
                f"{precipitation_type.capitalize()} "
                "until "
                f"{format_time(end)}"
            )
            start = first_start
        else:
            summary = (
                f"{precipitation_type.capitalize()} "
                "from "
                f"{format_time(first_start)}"
                " to "
                f"{format_time(end)}"
            )
            start = first_start

        return (
            summary,
            {
                "location": current_location,
                "precipitation_type": precipitation_type,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "amount": round(
                    total_amount,
                    2,
                ),
            },
        )


def _precipitation_type(
    rain: float,
    snowfall: float,
    weather_code: int | None,
) -> str:
    """Determine the precipitation type."""

    if rain > 0 and snowfall > 0:
        return "mixed"

    if snowfall > 0:
        return "snow"

    if rain > 0:
        return "rain"

    # Use the WMO weather code as a fallback when the precipitation
    # amount is zero or extremely small.
    if weather_code in (
        51,
        53,
        55,
        56,
        57,
        61,
        63,
        65,
        66,
        67,
        80,
        81,
        82,
    ):
        return "rain"

    if weather_code in (
        71,
        73,
        75,
        77,
        85,
        86,
    ):
        return "snow"

    if weather_code in (
        95,
        96,
        99,
    ):
        return "rain"

    return "precipitation"


def _combine_precipitation_types(
    types: set[str],
) -> str:
    """Combine precipitation types for a precipitation period."""

    types.discard(
        "precipitation"
    )

    if "rain" in types and "snow" in types:
        return "mixed"

    if "snow" in types:
        return "snow"

    if "rain" in types:
        return "rain"

    return "precipitation"


def _parse_calendar_datetime(
    value: Any,
) -> datetime | None:
    """Parse a calendar datetime or all-day date."""
    if isinstance(
        value,
        datetime,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        parsed = dt_util.parse_datetime(
            value
        )

        if parsed is not None:
            return parsed

        parsed_date = dt_util.parse_date(
            value
        )

        if parsed_date is not None:
            timezone = dt_util.DEFAULT_TIME_ZONE

            return datetime.combine(
                parsed_date,
                datetime.min.time(),
                tzinfo=timezone,
            )

    return None


def _parse_open_meteo_local_time(
    value: Any,
    timezone_name: str,
) -> datetime | None:
    """Parse an Open-Meteo local timestamp."""
    if not isinstance(
        value,
        str,
    ):
        return None

    parsed = dt_util.parse_datetime(
        value
    )

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        timezone = dt_util.get_time_zone(
            timezone_name
        )

        if timezone is None:
            return None

        parsed = parsed.replace(
            tzinfo=timezone
        )

    return parsed
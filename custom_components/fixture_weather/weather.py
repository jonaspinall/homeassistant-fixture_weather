"""Weather entity for Fixture Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN
from .coordinator import FixtureWeatherCoordinator


def _condition_from_code(
    code: int | None,
    is_day: bool | None = None,
) -> str:
    """Convert an Open-Meteo WMO weather code to an HA condition."""
    if code is None:
        return ATTR_CONDITION_EXCEPTIONAL

    if code == 0:
        return (
            ATTR_CONDITION_SUNNY
            if is_day is not False
            else ATTR_CONDITION_CLEAR_NIGHT
        )

    if code == 1:
        return ATTR_CONDITION_PARTLYCLOUDY

    if code == 2:
        return ATTR_CONDITION_PARTLYCLOUDY

    if code == 3:
        return ATTR_CONDITION_CLOUDY

    if code in (45, 48):
        return ATTR_CONDITION_FOG

    if code in (51, 53, 55, 56, 57):
        return ATTR_CONDITION_RAINY

    if code in (61, 63):
        return ATTR_CONDITION_RAINY

    if code in (65, 66, 67):
        return ATTR_CONDITION_POURING

    if code in (71, 73, 75, 77):
        return ATTR_CONDITION_SNOWY

    if code in (80, 81):
        return ATTR_CONDITION_RAINY

    if code == 82:
        return ATTR_CONDITION_POURING

    if code in (85, 86):
        return ATTR_CONDITION_SNOWY

    if code == 95:
        return ATTR_CONDITION_LIGHTNING

    if code in (96, 99):
        return ATTR_CONDITION_LIGHTNING_RAINY

    return ATTR_CONDITION_CLOUDY


class FixtureWeatherEntity(
    CoordinatorEntity[FixtureWeatherCoordinator],
    WeatherEntity,
):
    """Represent Fixture Weather."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = ATTRIBUTION

    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_DAILY
    )

    _attr_native_temperature_unit = "°C"
    _attr_native_wind_speed_unit = "km/h"
    _attr_native_precipitation_unit = "mm"

    def __init__(
        self,
        coordinator: FixtureWeatherCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_weather"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

    @property
    def native_temperature(self) -> float | None:
        """Return current temperature."""
        return self.coordinator.data.current.get(
            "temperature_2m"
        )

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return apparent temperature."""
        return self.coordinator.data.current.get(
            "apparent_temperature"
        )

    @property
    def humidity(self) -> float | None:
        """Return current humidity."""
        return self.coordinator.data.current.get(
            "relative_humidity_2m"
        )

    @property
    def cloud_coverage(self) -> int | None:
        """Return cloud coverage."""
        return self.coordinator.data.current.get(
            "cloud_cover"
        )

    @property
    def native_wind_speed(self) -> float | None:
        """Return wind speed."""
        return self.coordinator.data.current.get(
            "wind_speed_10m"
        )

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return wind gust speed."""
        return self.coordinator.data.current.get(
            "wind_gusts_10m"
        )

    @property
    def wind_bearing(self) -> float | None:
        """Return wind direction."""
        return self.coordinator.data.current.get(
            "wind_direction_10m"
        )

    @property
    def condition(self) -> str:
        """Return current weather condition."""
        return _condition_from_code(
            self.coordinator.data.current.get("weather_code"),
            bool(
                self.coordinator.data.current.get(
                    "is_day"
                )
            ),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "base_location": (
                self.coordinator.base_location_name
            ),
            "forecast_location": (
                self.coordinator.data.current_location
            ),
            "precipitation_probability": self.coordinator.data.current.get(
                "precipitation_probability"
            ),
            "precipitation": self.coordinator.data.current.get(
                "precipitation"
            ),
        }

    async def async_forecast_hourly(
        self,
    ) -> list[dict[str, Any]]:
        """Return the hourly forecast from the current hour."""
        forecasts: list[dict[str, Any]] = []

        # The coordinator deliberately retains the complete merged
        # forecast, including hours before the current hour. This is
        # useful for other consumers of the coordinator data.
        #
        # The HA WeatherEntity, however, should expose the hourly
        # forecast beginning at the current local hour, as standard
        # HA weather entities do.
        now = dt_util.now()

        current_hour = now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        for entry in self.coordinator.data.hourly:
            local_datetime = entry.get(
                "local_datetime"
            )

            if not isinstance(
                local_datetime,
                type(current_hour),
            ):
                continue

            if local_datetime < current_hour:
                continue

            forecasts.append(
                {
                    "datetime": entry["datetime"],
                    "condition": _condition_from_code(
                        entry.get("weather_code"),
                        bool(
                            entry.get("is_day")
                        ),
                    ),
                    "native_temperature": entry.get(
                        "temperature_2m"
                    ),
                    "native_apparent_temperature": entry.get(
                        "apparent_temperature"
                    ),
                    "native_wind_speed": entry.get(
                        "wind_speed_10m"
                    ),
                    "native_wind_gust_speed": entry.get(
                        "wind_gusts_10m"
                    ),
                    "wind_bearing": entry.get(
                        "wind_direction_10m"
                    ),
                    "humidity": entry.get(
                        "relative_humidity_2m"
                    ),
                    "cloud_coverage": entry.get(
                        "cloud_cover"
                    ),
                    "native_precipitation": entry.get(
                        "precipitation"
                    ),
                    "precipitation_probability": entry.get(
                        "precipitation_probability"
                    ),
                }
            )

        return forecasts

    async def async_forecast_daily(
        self,
    ) -> list[dict[str, Any]]:
        """Return the daily forecast."""
        forecasts: list[dict[str, Any]] = []

        for entry in self.coordinator.data.daily:
            forecasts.append(
                {
                    "datetime": entry["datetime"],
                    "condition": _condition_from_code(
                        entry.get("weather_code"),
                        bool(
                            entry.get("is_day")
                        ),
                    ),
                    "native_temperature": entry.get(
                        "temperature_2m_max"
                    ),
                    "native_templow": entry.get(
                        "temperature_2m_min"
                    ),
                    "native_apparent_temperature": entry.get(
                        "apparent_temperature_max"
                    ),
                    "native_precipitation": entry.get(
                        "precipitation_sum"
                    ),
                    "precipitation_probability": entry.get(
                        "precipitation_probability_max"
                    ),
                    "native_wind_speed": entry.get(
                        "wind_speed_10m_max"
                    ),
                    "native_wind_gust_speed": entry.get(
                        "wind_gusts_10m_max"
                    ),
                }
            )

        return forecasts


async def async_setup_entry(
    hass,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the weather entity."""
    coordinator: FixtureWeatherCoordinator = entry.runtime_data

    async_add_entities(
        [
            FixtureWeatherEntity(
                coordinator,
                entry,
            )
        ]
    )
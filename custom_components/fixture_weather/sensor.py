"""Sensors for Fixture Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import FixtureWeatherCoordinator


class PrecipitationSummarySensor(
    CoordinatorEntity[FixtureWeatherCoordinator],
    SensorEntity,
):
    """Summarise upcoming precipitation."""

    _attr_has_entity_name = True
    _attr_name = "Precipitation"
    _attr_icon = "mdi:weather-rainy"
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: FixtureWeatherCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{entry.entry_id}_precipitation"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

    @property
    def native_value(self) -> str:
        """Return the precipitation summary."""
        return self.coordinator.data.precipitation_summary

    @property
    def icon(self) -> str:
        """Return an icon appropriate to the precipitation type."""
        precipitation_type = (
            self.coordinator.data.precipitation_attributes.get(
                "precipitation_type"
            )
        )

        icons = {
            "rain": "mdi:weather-rainy",
            "showers": "mdi:weather-pouring",
            "drizzle": "mdi:weather-rainy",
            "snow": "mdi:weather-snowy",
            "snow_showers": "mdi:weather-snowy-rainy",
            "freezing_rain": "mdi:weather-rainy",
            "freezing_drizzle": "mdi:weather-rainy",
            "sleet": "mdi:weather-snowy-rainy",
            "thunderstorm": "mdi:weather-lightning-rainy",
            "precipitation": "mdi:weather-rainy",
        }

        return icons.get(
            precipitation_type,
            "mdi:weather-partly-cloudy",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return precipitation details."""
        return self.coordinator.data.precipitation_attributes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up precipitation sensors."""
    coordinator: FixtureWeatherCoordinator = entry.runtime_data

    async_add_entities(
        [
            PrecipitationSummarySensor(
                coordinator,
                entry,
            )
        ]
    )
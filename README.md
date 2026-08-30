# Fixture Weather

Fixture Weather is a Home Assistant custom integration that creates a weather entity for a fixed location or follows locations from calendar events. It is useful for sports fixtures, travel plans, and other calendars where the relevant weather location changes from day to day.

## Features

- Current conditions plus hourly and 14-day daily forecasts.
- Optional calendar-based forecast locations.
- A precipitation summary sensor with the next significant precipitation period.
- Geocoding through Nominatim with Open-Meteo as a fallback.
- Persistent geocoding cache to reduce repeated requests.
- Weather and precipitation entities grouped under the same Home Assistant device.

## Installation With HACS

1. Open HACS in Home Assistant.
2. Open **Integrations** and select the menu in the upper-right corner.
3. Select **Custom repositories**.
4. Add this GitHub repository URL and select **Integration** as the category.
5. Search for **Fixture Weather** and install it.
6. Restart Home Assistant.

Once the repository is published in the default HACS store, the custom repository step will no longer be needed.

## Manual Installation

Copy the `custom_components/fixture_weather` directory into the `custom_components` directory of your Home Assistant configuration directory, then restart Home Assistant.

## Configuration

After installation:

1. Go to **Settings > Devices & services**.
2. Select **Add integration**.
3. Search for **Fixture Weather**.
4. Enter a name and the fallback base location.
5. Optionally select a calendar.

When a calendar is configured, the current forecast location follows the active event while it is running. After an event ends, its location stays in effect through a 3-hour grace period, unless a later event starts sooner and takes precedence. Future days/hours in the forecast are for whichever event is active or coming up. If a calendar location cannot be geocoded, the base location is used.

## Entities

Each config entry creates:

- One weather entity with current, hourly, and daily forecasts.
- One precipitation summary sensor.

The weather entity also exposes the base location, active forecast location, current precipitation probability, and current precipitation amount as attributes.

## Data Providers

Weather and geocoding fallback data are provided by [Open-Meteo](https://open-meteo.com/). Primary geocoding uses [Nominatim](https://nominatim.openstreetmap.org/), which relies on [OpenStreetMap](https://www.openstreetmap.org/) data.

Please respect the usage policies of both geocoding services. Nominatim requests are rate-limited by the integration and include a User-Agent.

## Limitations

- The configured Home Assistant timezone is used to align forecast dates and calendar days.
- Calendar event locations must be text that can be geocoded.
- The integration requires network access to the weather and geocoding services.

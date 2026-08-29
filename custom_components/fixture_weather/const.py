"""Constants for the Fixture Weather integration."""

from datetime import timedelta

DOMAIN = "fixture_weather"

CONF_BASE_LOCATION = "base_location"
CONF_CALENDAR = "calendar"

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=30)
FORECAST_DAYS = 14
EVENT_LOCATION_GRACE_PERIOD = timedelta(hours=3)

# High-resolution precipitation forecast window.
MINUTELY_PRECIPITATION_HOURS = 48
MINUTELY_PRECIPITATION_THRESHOLD = 0.01

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODING_URL = (
    "https://geocoding-api.open-meteo.com/v1/search"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

GEOCODE_CACHE_VERSION = 1
GEOCODE_CACHE_KEY = f"{DOMAIN}.geocoding"

ATTR_BASE_LOCATION = "base_location"
ATTR_FORECAST_LOCATION = "forecast_location"
ATTR_FORECAST_DATE = "forecast_date"

ATTR_FIXTURE = "fixture"
ATTR_FIXTURE_LOCATION = "fixture_location"
ATTR_FIXTURE_DATE = "fixture_date"

PRECIPITATION_PROBABILITY_THRESHOLD = 50
PRECIPITATION_AMOUNT_THRESHOLD = 0.1

# Number of 15-minute precipitation forecast periods to inspect.
# 48 periods = 12 hours.
PRECIPITATION_FORECAST_PERIODS = 48

ATTRIBUTION = (
    "Weather data by Open-Meteo; map data © OpenStreetMap contributors"
)
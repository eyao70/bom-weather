import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bom_weather_api import BomClient, Coordinate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
POSTCODE_FILE = BASE_DIR / "postcodes.json"


def load_postcodes():
    if not POSTCODE_FILE.exists():
        return {}

    with POSTCODE_FILE.open(encoding="utf-8") as file:
        return json.load(file)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="BOM Weather Dashboard",
    description="Weather information from official BOM data feeds",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
async def health():
    return {"status": "healthy"}


def iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def get_value(obj, name):
    return getattr(obj, name, None)


@app.get("/api/weather")
async def get_weather(
    postcode: str = Query(..., pattern=r"^\d{4}$")
):
    postcode_data = load_postcodes()
    location = postcode_data.get(postcode)

    if not location:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Postcode {postcode} is not in the local postcode "
                "database. Add it to app/postcodes.json."
            ),
        )

    try:
        coordinate = Coordinate(
            latitude=float(location["lat"]),
            longitude=float(location["lon"]),
        )

        async with BomClient(timeout=30) as client:
            towns = await client.get_forecast_locations()

            nearest_towns = BomClient.nearest(
                coordinate, towns, limit=1
            )

            if not nearest_towns:
                raise HTTPException(
                    status_code=404,
                    detail="No nearby BOM forecast town was found.",
                )

            town, distance_km = nearest_towns[0]

            # Retrieve the seven-day forecast using official feeds.
            daily = await client.get_daily_forecast(
                town, extras=False
            )

            # Select the nearest observation station in the same state.
            stations = await client.get_stations(town.product_state)

            nearest_stations = BomClient.nearest(
                town.coordinate, stations, limit=1
            )

            observation_data = None

            if nearest_stations:
                station, station_distance = nearest_stations[0]

                try:
                    observation = await client.get_observation(
                        town.product_state, station.id
                    )

                    observation_data = {
                        "station": station.name,
                        "station_id": station.id,
                        "distance_km": round(station_distance, 1),
                        "observed_at": iso(
                            get_value(observation, "observed_at")
                        ),
                        "temperature": get_value(
                            observation, "temperature"
                        ),
                        "apparent_temperature": get_value(
                            observation, "apparent_temperature"
                        ),
                        "humidity": get_value(observation, "humidity"),
                        "wind_speed": get_value(
                            observation, "wind_speed"
                        ),
                        "wind_direction": get_value(
                            observation, "wind_direction"
                        ),
                        "wind_gust": get_value(
                            observation, "wind_gust"
                        ),
                        "rain_since_9am": get_value(
                            observation, "rain_since_9am"
                        ),
                    }

                except Exception as exc:
                    logger.warning(
                        "Unable to retrieve station observation: %s",
                        exc,
                    )

            forecast_days = []

            for day in daily.days[:7]:
                forecast_days.append({
                    "date": iso(day.date),
                    "description": day.short_text,
                    "details": day.extended_text,
                    "min": day.temp_min,
                    "max": day.temp_max,
                    "rain_chance": day.rain_chance,
                    "rain_amount": day.rain_amount_range,
                    "uv_index": day.uv_index,
                })

            return {
                "postcode": postcode,
                "suburb": location.get("suburb", ""),
                "state": location.get("state", ""),
                "latitude": location["lat"],
                "longitude": location["lon"],
                "forecast_town": town.name,
                "forecast_distance_km": round(distance_km, 1),
                "forecast_issued_at": iso(daily.issued_at),
                "current_condition": (
                    {
                        "description": daily.days[0].short_text,
                        "icon": daily.days[0].icon_descriptor,
                    }
                    if daily.days
                    else None
                ),
                "observation": observation_data,
                "forecast": forecast_days,
                "source": "Australian Bureau of Meteorology official data feeds",
            }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("BOM weather query failed")

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to retrieve weather data from the official "
                f"BOM feeds. Check connectivity and try again. ({type(exc).__name__})"
            ),
        ) from exc
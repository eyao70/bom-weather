import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bom_weather_api import BomClient, Coordinate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
POSTCODE_FILE = BASE_DIR / "postcodes.json"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_COOKIE = "bom_weather_verified"
TURNSTILE_SESSION_TTL = 12 * 60 * 60


def load_postcodes():
    if not POSTCODE_FILE.exists():
        return {}

    with POSTCODE_FILE.open(encoding="utf-8") as file:
        return json.load(file)


class TurnstileToken(BaseModel):
    token: str = Field(min_length=1, max_length=2048)


def _turnstile_secret() -> str:
    return os.environ.get("TURNSTILE_SECRET_KEY", "").strip()


def _turnstile_session_signature(timestamp: str, secret: str) -> str:
    signing_key = hmac.new(
        secret.encode("utf-8"),
        b"bom-weather-session-cookie",
        hashlib.sha256,
    ).digest()
    return hmac.new(
        signing_key, timestamp.encode("ascii"), hashlib.sha256
    ).hexdigest()


def _is_verified_session(request: Request) -> bool:
    secret = _turnstile_secret()
    cookie = request.cookies.get(TURNSTILE_COOKIE, "")

    if not secret or "." not in cookie:
        return False

    timestamp, signature = cookie.split(".", 1)
    if not timestamp.isascii() or not timestamp.isdigit():
        return False

    try:
        issued_at = int(timestamp)
    except ValueError:
        return False

    age = int(time.time()) - issued_at
    if age < 0 or age >= TURNSTILE_SESSION_TTL:
        return False

    expected_signature = _turnstile_session_signature(timestamp, secret)
    return hmac.compare_digest(signature, expected_signature)


def _verify_turnstile_token(token: str, secret: str) -> dict:
    body = urllib.parse.urlencode({
        "secret": secret,
        "response": token,
    }).encode("ascii")
    request = urllib.request.Request(
        TURNSTILE_VERIFY_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="BOM Weather Dashboard",
    description="Weather information from official BOM data feeds",
    version="1.1.2",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/turnstile-config")
async def turnstile_config(request: Request, response: Response):
    site_key = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
    secret = _turnstile_secret()
    response.headers["Cache-Control"] = "no-store"
    return {
        "configured": bool(site_key and secret),
        "site_key": site_key,
        "verified": _is_verified_session(request),
    }


@app.post("/api/verify-turnstile")
async def verify_turnstile(
    payload: TurnstileToken,
    request: Request,
    response: Response,
):
    site_key = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
    secret = _turnstile_secret()
    if not site_key or not secret:
        raise HTTPException(
            status_code=503,
            detail="Turnstile is not configured on this server.",
        )

    try:
        result = await asyncio.to_thread(
            _verify_turnstile_token, payload.token, secret
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Turnstile verification service is unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Turnstile verification is temporarily unavailable. Try again.",
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Turnstile returned an invalid response: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Turnstile returned an invalid verification response.",
        ) from exc

    if not isinstance(result, dict):
        logger.error("Turnstile returned a non-object verification response")
        raise HTTPException(
            status_code=502,
            detail="Turnstile returned an invalid verification response.",
        )

    if result.get("success") is not True:
        raise HTTPException(
            status_code=400,
            detail="Turnstile verification failed. Please try again.",
        )

    hostname = str(result.get("hostname", "")).lower().rstrip(".")
    expected_hostname = (
        os.environ.get("TURNSTILE_EXPECTED_HOSTNAME", "").strip()
        or request.url.hostname
        or ""
    ).lower().rstrip(".")
    if not hostname or hostname != expected_hostname:
        logger.warning(
            "Turnstile hostname mismatch: received %r, expected %r",
            hostname,
            expected_hostname,
        )
        raise HTTPException(
            status_code=400,
            detail="Turnstile verification hostname did not match this site.",
        )

    timestamp = str(int(time.time()))
    signature = _turnstile_session_signature(timestamp, secret)
    response.set_cookie(
        key=TURNSTILE_COOKIE,
        value=f"{timestamp}.{signature}",
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return {"verified": True}


def iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def get_value(obj, name):
    return getattr(obj, name, None)


@app.get("/api/weather")
async def get_weather(
    request: Request,
    postcode: str = Query(..., pattern=r"^\d{4}$"),
):
    if not _is_verified_session(request):
        raise HTTPException(
            status_code=403,
            detail="Complete Turnstile verification before requesting weather.",
        )

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
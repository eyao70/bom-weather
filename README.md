# BOM Weather

<img src="docs/screenshots/logo.png" alt="BOM Weather logo" width="48">

**A simple, self-hosted Australian weather dashboard in one Docker container.**
Look up a four-digit postcode to see nearby Bureau of Meteorology (BOM)
observations and a seven-day forecast.

Run it on your own machine or home server, then open the dashboard in any
browser—no app installation required.

## Screenshots

The screenshot is an illustrative preview using sample values, not live BOM
readings.

![Dashboard preview](docs/screenshots/dashboard.png)

## What it includes

- **Postcode search:** enter an Australian four-digit postcode to find nearby
  weather information.
- **Current conditions:** see observations from the nearest available BOM
  station, including temperature, humidity, wind, and rainfall when available.
- **Seven-day forecast:** view forecast details, rain chances, and daily
  temperature highs and lows.
- **Weather visuals:** explore a temperature chart and animated rain radar.
- **Theme settings:** switch between light and dark themes from the settings menu.
- **Turnstile verification:** verify visitors before allowing weather requests.
- **Lightweight deployment:** run a single container on your own computer or
  home server, with automatic restart support.

Forecasts come from official BOM data feeds. Station observations and external
map imagery may be delayed or temporarily unavailable. The postcode lookup uses
the postcode data bundled in the image.

## Configure Turnstile

Weather requests require a valid Cloudflare Turnstile verification. Create a
Turnstile widget in the Cloudflare dashboard and add the hostname used to open
the dashboard. Copy `.env.example` to `.env` and set your widget's site key and
secret key:

```sh
cp -n .env.example .env
```

Keep the secret key private; `.env` is excluded from Git. Set
`TURNSTILE_EXPECTED_HOSTNAME` to the hostname users visit, without a scheme,
port, or path. It can be left blank for local development, where the request
hostname is checked automatically when using your own widget. For local testing
with Cloudflare's
[test keys](https://developers.cloudflare.com/turnstile/troubleshooting/testing/),
set `TURNSTILE_EXPECTED_HOSTNAME=example.com`; Cloudflare's test keys return
that hostname.

## Deploy the container image

Docker is required. Configure `.env` as described above, then pull the
published image and start the container:

```sh
docker pull eyao70/bom-weather:latest
docker run -d \
  --env-file .env \
  --name bom-weather \
  --restart unless-stopped \
  -p 8088:8088 \
  eyao70/bom-weather:latest
```

Open [http://localhost:8088](http://localhost:8088). The container listens on
port `8088`; change the left side of `-p 8088:8088` if that host port is already
in use. The `/health` endpoint can be used for health checks.

To update to the latest published image:

```sh
docker pull eyao70/bom-weather:latest
docker rm -f bom-weather
docker run -d \
  --env-file .env \
  --name bom-weather \
  --restart unless-stopped \
  -p 8088:8088 \
  eyao70/bom-weather:latest
```

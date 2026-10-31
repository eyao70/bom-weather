# BOM Weather

<img src="docs/screenshots/logo.png" alt="BOM Weather logo" width="48">

A FastAPI dashboard for Australian Bureau of Meteorology forecasts and
observations.

## Screenshots

Illustrative dashboard previews using sample values; these are not live BOM
readings.

![Dashboard preview](docs/screenshots/dashboard.png)

## Deploy the container image

Pull and start the image from Docker Hub:

```sh
docker pull eyao70/bom-weather:latest
docker run -d \
  --name bom-weather \
  --restart unless-stopped \
  -p 8088:8088 \
  eyao70/bom-weather:latest
```

Open [http://localhost:8088](http://localhost:8088). To deploy from GitHub
Container Registry instead, replace `eyao70/bom-weather:latest` with
`ghcr.io/eyao70/bom-weather:latest` in the commands above.

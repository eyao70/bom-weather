# BOM Weather

![BOM Weather logo](docs/screenshots/logo.png)

A FastAPI dashboard for Australian Bureau of Meteorology forecasts and
observations.

## Screenshots

Illustrative dashboard previews using sample values; these are not live BOM
readings.

![Dashboard preview](docs/screenshots/dashboard.png)

## Build and publish to Docker Hub

From this directory, build the image with tags for both Docker Hub and GitHub
Container Registry (GHCR):

```sh
docker compose build --pull
```

Sign in to Docker Hub and GHCR, then push each tag:

```sh
docker login -u eyao70
echo "$GHCR_TOKEN" | docker login ghcr.io -u eyao70 --password-stdin
docker push eyao70/bom-weather:latest
docker push ghcr.io/eyao70/bom-weather:latest
```

For GHCR, use a GitHub Personal Access Token (classic) with `write:packages`
permission as `GHCR_TOKEN`. Set package visibility in GitHub as desired. Choose
whether the Docker Hub repository is public or private there. Do not put
passwords or access tokens in this file or in the image.

## Run the published image

```sh
docker run -d \
  --name bom-weather \
  --restart unless-stopped \
  -p 8088:8088 \
  eyao70/bom-weather:latest
```

Open [http://localhost:8088](http://localhost:8088). The image includes the
postcode data bundled at build time. To rebuild with updated data, run
`convert_postcodes.py` before building the image.

## Run with Docker Compose

From this directory, build and start the app with:

```sh
docker compose up -d --build
```

The Compose setup publishes the app on port `8088` and checks its `/health`
endpoint.

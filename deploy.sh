#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:?usage: deploy.sh <image-tag>}"
IMAGE_REPO="ghcr.io/newton-and-chero/dawa-iko-backend"

cd /opt/calle/backend

export API_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

COMPOSE="docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.deploy.yml"

GHCR_USER="$(sed -n 's/^GHCR_USER=//p' .env)"
GHCR_TOKEN="$(sed -n 's/^GHCR_TOKEN=//p' .env)"
if [ -n "$GHCR_TOKEN" ]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

$COMPOSE pull
$COMPOSE run --rm api uv run alembic upgrade head
$COMPOSE up -d --remove-orphans
$COMPOSE ps
docker image prune -f

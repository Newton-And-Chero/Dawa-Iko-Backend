#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=/opt/calle
IMAGE_TAG="${1:?usage: deploy.sh <image-tag>}"
IMAGE_REPO="ghcr.io/newton-and-chero/dawa-iko-backend"

cd "$REPO_DIR"
git fetch --depth 1 origin main
git reset --hard origin/main

cd "$REPO_DIR/backend"

export API_IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

COMPOSE="docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.deploy.yml"

if grep -q '^GHCR_TOKEN=' .env; then
  set -a; . ./.env; set +a
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

$COMPOSE pull
$COMPOSE run --rm api uv run alembic upgrade head
$COMPOSE up -d --remove-orphans
$COMPOSE ps
docker image prune -f

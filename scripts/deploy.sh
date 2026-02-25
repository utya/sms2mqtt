#!/usr/bin/env bash
# Deploy script for server with Docker (no CI/CD).
# Pulls latest changes, rebuilds image, recreates container.
# Usage:
#   ./scripts/deploy.sh              # from repo root
#   ./scripts/deploy.sh --no-cache    # full rebuild without cache
#   ./scripts/deploy.sh main          # pull branch 'main' (default: current branch)
#
# Requires: git, docker, docker compose. Run from repo root or scripts/ directory.
# Optional: .env in repo root for MQTT and device settings (see compose.yml).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f compose.yml ]]; then
  echo "Error: compose.yml not found. Run from repo root or scripts/." >&2
  exit 1
fi

BRANCH=""
NO_CACHE=""
for arg in "$@"; do
  if [[ "$arg" == "--no-cache" ]]; then
    NO_CACHE="--no-cache"
  elif [[ "$arg" != --* ]]; then
    BRANCH="$arg"
  fi
done

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-sms2mqtt}"
COMPOSE_CMD="docker compose -f compose.yml"
# Production overlay: docker compose -f compose.yml -f compose.production.yml
# Uncomment next line and set VERSION in .env if you use pre-built images from registry:
# COMPOSE_CMD="docker compose -f compose.yml -f compose.production.yml"

echo "=== Deploy $COMPOSE_PROJECT_NAME ==="
echo "Root: $ROOT_DIR"
echo "Branch: ${BRANCH:-$(git branch --show-current)}"
echo "---"

if [[ -n "$BRANCH" ]]; then
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
else
  git pull
fi

echo "--- Building image ---"
$COMPOSE_CMD build $NO_CACHE

echo "--- Stopping current container ---"
$COMPOSE_CMD down

echo "--- Starting new container ---"
$COMPOSE_CMD up -d

echo "--- Pruning old images ---"
docker image prune -f

echo "--- Done. Status: ---"
$COMPOSE_CMD ps

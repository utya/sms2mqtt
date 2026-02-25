#!/usr/bin/env bash
# Deploy script for persistence stack (Postgres + sms2mqtt-persistence). No CI/CD.
# Pulls latest changes, rebuilds listener image, recreates containers.
# Usage:
#   ./scripts/deploy-persistence.sh              # from repo root
#   ./scripts/deploy-persistence.sh --no-cache   # full rebuild without cache
#   ./scripts/deploy-persistence.sh main         # pull branch 'main' (default: current branch)
#
# Requires: git, docker, docker compose. Run from repo root or scripts/ directory.
# Optional: .env in repo root (PGPASSWORD, MQTT_*, LOG_LEVEL — see docker-compose.persistence.yml).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="docker-compose.persistence.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Error: $COMPOSE_FILE not found. Run from repo root or scripts/." >&2
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
COMPOSE_CMD="docker compose -f $COMPOSE_FILE --profile persistence"

echo "=== Deploy persistence ($COMPOSE_PROJECT_NAME) ==="
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

echo "--- Building image (sms2mqtt-persistence) ---"
$COMPOSE_CMD build $NO_CACHE

echo "--- Stopping current containers ---"
$COMPOSE_CMD down

echo "--- Starting containers ---"
$COMPOSE_CMD up -d

echo "--- Pruning old images ---"
docker image prune -f

echo "--- Done. Status: ---"
$COMPOSE_CMD ps

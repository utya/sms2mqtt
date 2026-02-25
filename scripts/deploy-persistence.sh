#!/usr/bin/env bash
# Deploy script for persistence stack (Postgres + sms2mqtt-persistence). No CI/CD.
# Copies persistence compose and app into a stack directory so Dockge can show the stack,
# then pulls, builds, and recreates containers.
# Usage:
#   ./scripts/deploy-persistence.sh              # from repo root
#   ./scripts/deploy-persistence.sh --no-cache   # full rebuild without cache
#   ./scripts/deploy-persistence.sh main         # pull branch 'main' (default: current branch)
#
# Stack directory (where compose is copied so Dockge picks it up):
#   - If DOCKGE_STACKS_DIR is set: $DOCKGE_STACKS_DIR/sms2mqtt-persistence
#   - Else: sibling of repo, e.g. /opt/stacks/sms2mqtt-persistence when repo is /opt/stacks/sms2mqtt
# Optional: .env in repo root (PGPASSWORD, MQTT_*, LOG_LEVEL); copied to stack dir for compose.

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

# Where Dockge (or sibling folder) expects the stack: one folder = one stack
STACKS_PARENT="${DOCKGE_STACKS_DIR:-$(dirname "$ROOT_DIR")}"
PERSISTENCE_STACK_DIR="$STACKS_PARENT/sms2mqtt-persistence"

echo "=== Deploy persistence ==="
echo "Repo root: $ROOT_DIR"
echo "Stack dir (for Dockge): $PERSISTENCE_STACK_DIR"
echo "Branch: ${BRANCH:-$(git branch --show-current)}"
echo "---"

if [[ -n "$BRANCH" ]]; then
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
else
  git pull
fi

echo "--- Copying compose and app into stack dir ---"
mkdir -p "$PERSISTENCE_STACK_DIR"
cp "$COMPOSE_FILE" "$PERSISTENCE_STACK_DIR/compose.yml"
cp -r sms2mqtt-persistence "$PERSISTENCE_STACK_DIR/"
# Build stack .env: copy repo .env and force COMPOSE_PROJECT_NAME from SMS2MQTT_PERSISTENCE so persistence does not stop the main bridge
if [[ -f .env ]]; then
  cp .env "$PERSISTENCE_STACK_DIR/.env"
fi
PERSISTENCE_PROJECT="sms2mqtt-persistence"
if [[ -f .env ]]; then
  v=$(grep -E '^SMS2MQTT_PERSISTENCE=' .env 2>/dev/null | cut -d= -f2-)
  [[ -n "$v" ]] && PERSISTENCE_PROJECT="$v"
fi
{ grep -v '^COMPOSE_PROJECT_NAME=' "$PERSISTENCE_STACK_DIR/.env" 2>/dev/null || true
  echo "COMPOSE_PROJECT_NAME=$PERSISTENCE_PROJECT"
} > "$PERSISTENCE_STACK_DIR/.env.tmp" && mv "$PERSISTENCE_STACK_DIR/.env.tmp" "$PERSISTENCE_STACK_DIR/.env"

echo "--- Building image (sms2mqtt-persistence) ---"
cd "$PERSISTENCE_STACK_DIR"
docker compose -f compose.yml build $NO_CACHE

echo "--- Stopping current containers ---"
docker compose -f compose.yml down

echo "--- Starting containers ---"
docker compose -f compose.yml up -d

echo "--- Pruning old images ---"
docker image prune -f

echo "--- Done. Status: ---"
docker compose -f compose.yml ps

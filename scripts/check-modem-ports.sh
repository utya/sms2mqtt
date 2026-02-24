#!/usr/bin/env bash
# Check which /dev/ttyUSB* port works with Gammu (for use before configuring Docker).
# Run on the host where the modem is attached. Requires gammu installed.
# Uses a minimal config (no PIN); if SIM has PIN, you get "SIM not accessible" even though
# the port is correct (modem_stat.sh may still show operator/signal if it uses a config with PIN).
# Usage: ./scripts/check-modem-ports.sh [ttyUSB0 ttyUSB1 ttyUSB2]
#        Or with sudo if you get "permission denied": sudo ./scripts/check-modem-ports.sh

set -e

if [[ $# -gt 0 ]]; then
  PORTS=("$@")
else
  PORTS=(/dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyUSB2)
fi
GAMMU="${GAMMU:-gammu}"
RCFILE="${RCFILE:-/tmp/gammurc-check}"

if ! command -v "$GAMMU" &>/dev/null; then
  echo "Error: gammu not found. Install it (e.g. apt install gammu)."
  exit 1
fi

echo "Checking modem ports with: $GAMMU"
echo "Ports: ${PORTS[*]}"
echo "---"

for dev in "${PORTS[@]}"; do
  if [[ ! -e "$dev" ]]; then
    echo "[$dev] SKIP (device not found)"
    continue
  fi
  printf '[%s] ' "$dev"
  cat > "$RCFILE" << EOF
[gammu]
device = $dev
connection = at
EOF
  out=$("$GAMMU" -c "$RCFILE" identify 2>&1) || true
  if echo "$out" | grep -q "Manufacturer\|IMEI\|SIM IMSI"; then
    echo "OK (modem + SIM seen)"
    echo "$out" | sed 's/^/  /'
  elif echo "$out" | grep -qi "NOSIM\|Can not access SIM"; then
    echo "PORT OK, SIM not accessible (often PIN required — add PIN= to .env for Docker)"
  elif echo "$out" | grep -qi "TIMEOUT\|No response"; then
    echo "TIMEOUT (port not for AT commands, do not use in Docker)"
  elif echo "$out" | grep -qi "permission\|Permission"; then
    echo "PERMISSION DENIED (run with: sudo $0 $*)"
  else
    echo "FAIL"
    echo "$out" | sed 's/^/  /'
  fi
  echo ""
done

rm -f "$RCFILE"
echo "Done. Use a port that shows OK or 'PORT OK, SIM not accessible' in compose; add PIN= to .env if SIM has PIN."

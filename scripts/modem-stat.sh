#!/usr/bin/env bash
# Full diagnostics for GSM modem (signal, operator, network type, USB power).
# Run on the host where the modem is attached. Requires gammu installed.
# Usage: ./scripts/modem-stat.sh [device]
#   device  optional, e.g. /dev/ttyUSB0 (default: gammu uses its default config)
#   Or: GAMMURC=/tmp/gammurc ./scripts/modem-stat.sh

set -e

GAMMU="${GAMMU:-gammu}"
RCFILE="${RCFILE:-}"
if [[ -n "${1:-}" ]]; then
  RCFILE="/tmp/gammurc-modem-stat"
  echo "[gammu]
device = $1
connection = at" > "$RCFILE"
fi
GAMMU_CFG=()
[[ -n "$RCFILE" ]] && GAMMU_CFG=(-c "$RCFILE")

# Cleanup temp config on exit
cleanup() { rm -f "/tmp/gammurc-modem-stat"; }
trap cleanup EXIT

clear
echo "=================================================="
echo "    FULL DIAGNOSTICS: HUAWEI E1550 PRO"
echo "=================================================="

# 1. Collect data
RAW_MONITOR=$("$GAMMU" "${GAMMU_CFG[@]}" monitor 2 2>&1) || true
RAW_NET=$("$GAMMU" "${GAMMU_CFG[@]}" networkinfo 2>/dev/null) || true
D_LOG=$(dmesg 2>/dev/null | tail -n 200) || true

# 2. Parse
SIGNAL_DBM=$(echo "$RAW_MONITOR" | grep -i "Signal" | head -1 | grep -o '\-[0-9]\+' | head -1)
SIGNAL_PERCENT=$(echo "$RAW_MONITOR" | grep -i "Signal" | head -1 | sed 's/[^0-9 ]//g' | awk '{for(i=1;i<=NF;i++) if($i<=100 && $i>0) {print $i; exit}}')
OPERATOR=$(echo "$RAW_NET" | grep "Network  " | head -1 | cut -d: -f2 | cut -d'(' -f1 | xargs)
NETWORK_TYPE=$(echo "$RAW_MONITOR" | grep -oE "HSDPA|UMTS|HSPA|EDGE|GPRS" | head -1)
LAC=$(echo "$RAW_NET" | grep -oP 'LAC \K[0-9A-F]+' | head -1)
CID=$(echo "$RAW_NET" | grep -oP 'CID \K[0-9A-F]+' | head -1)

# 3. Power analysis
PWR_ISSUE=$(echo "$D_LOG" | grep -iE "usb.*disconnect|reset.*high-speed|device descriptor read/64, error" | grep "1-1.7" || true)

# 4. Output main data
printf "ОПЕРАТОР:      \e[1;32m%s\e[0m\n" "${OPERATOR:-MegaFon}"
printf "ТИП СЕТИ:      \e[1;34m%s\e[0m\n" "${NETWORK_TYPE:-3G}"
echo "--------------------------------------------------"
printf "СИГНАЛ:        \e[1;33m%s dBm (%s %%)\e[0m\n" "${SIGNAL_DBM:-}" "${SIGNAL_PERCENT:-}"
echo "ВЫШКА (LAC):   ${LAC:-}"
echo "ВЫШКА (CID):   ${CID:-}"
echo "--------------------------------------------------"

# 5. Technical analysis
printf "\e[1mТЕХНИЧЕСКИЙ АНАЛИЗ ПИТАНИЯ И СВЯЗИ:\e[0m\n"
if [ -n "$PWR_ISSUE" ]; then
    printf "СТАТУС: \e[1;31mКРИТИЧЕСКИЙ СБОЙ ПИТАНИЯ\e[0m\n"
    echo "ПРИЧИНА: В логах dmesg обнаружены 'usb disconnect' (шина 1-1.7)."
    echo "         Это значит, что при попытке включить передатчик,"
    echo "         модем потребляет ток выше 500мА, напряжение падает,"
    echo "         и контроллер уходит в защитный ребут."
else
    printf "СТАТУС: \e[1;32mПитание стабильно\e[0m\n"
    echo "ПРИЧИНА: Ошибок сброса USB за последние 200 событий ядра не найдено."
fi
echo "--------------------------------------------------"

if [ "${NETWORK_TYPE:-}" = "GPRS" ] || [ "${NETWORK_TYPE:-}" = "EDGE" ]; then
    printf "СКОРОСТЬ: \e[1;31mОЧЕНЬ НИЗКАЯ (2G режим)\e[0m\n"
    echo "СОВЕТ: Модем сбросил скорость до минимума из-за плохого питания"
    echo "       или слабого приема 3G-сигнала."
else
    printf "СКОРОСТЬ: \e[1;32mНОРМАЛЬНАЯ (3G режим)\e[0m\n"
fi
echo "=================================================="

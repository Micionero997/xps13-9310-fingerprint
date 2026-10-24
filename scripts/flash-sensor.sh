#!/bin/bash
# Reflash the Goodix 27c6:532d with a known (all-zero) TLS PSK, so that
# libfprint can talk to it. The previous PSK (most likely written by the
# Windows driver) cannot be restored. Booting Windows will probably re-pair
# the sensor with a new key and break this driver until you flash again.
# Read README.md first.
#
# Run with sudo: sudo bash scripts/flash-sensor.sh [--dry-run]
#   --dry-run  only read firmware version and PSK state, change nothing
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
# goodix-fp-linux-dev/goodix-firmware, pinned
firmware_commit=7b9a828d1d14dee587d9c900505233188c23a92d
firmware_name=GF5298_GM168SEC_APP_13016.bin
firmware_sha256=0f28f8f52860afea86bd56d869cd7f4fe41ba943edd1d56100113e94ecfd6c0d
firmware="$root/flash/firmware/53xd/$firmware_name"

found=
for dev in /sys/bus/usb/devices/*; do
  if [ "$(cat "$dev/idVendor" 2>/dev/null)" = 27c6 ] &&
     [ "$(cat "$dev/idProduct" 2>/dev/null)" = 532d ]; then
    found=1
  fi
done
if [ -z "$found" ]; then
  echo "No Goodix 27c6:532d sensor found (check lsusb). Stopping." >&2
  exit 1
fi

if [ ! -f "$firmware" ] ||
   ! echo "$firmware_sha256  $firmware" | sha256sum --quiet -c - 2>/dev/null; then
  mkdir -p "$(dirname "$firmware")"
  curl -fsSL -o "$firmware" \
    "https://raw.githubusercontent.com/goodix-fp-linux-dev/goodix-firmware/$firmware_commit/53xd/$firmware_name"
  echo "$firmware_sha256  $firmware" | sha256sum --quiet -c - ||
    { echo "Firmware download does not match the expected hash." >&2; exit 1; }
fi

# fprintd would hold the sensor while it is in use
systemctl stop fprintd 2>/dev/null || true

cd "$root/flash"
exec python3 -B flash_532d.py "$@"

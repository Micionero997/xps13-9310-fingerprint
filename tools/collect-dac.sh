#!/bin/bash
# Guided collection of raw frames for re-tuning the matcher (see
# flash/collect_dac.py and tools/README.md). Writes biometric data to
# dump-dac/ in the repository root (git-ignored): delete it when done.
#
#   sudo bash tools/collect-dac.sh 1   session 1: enroll set + other fingers
#   sudo bash tools/collect-dac.sh 2   session 2, hours later: probe touches
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
case "${1:-}" in
  1) plan=(right-index:16 right-middle:8 left-index:8 right-thumb:8) ;;
  2) plan=(right-index-probe:8) ;;
  *) echo "usage: sudo bash tools/collect-dac.sh 1|2" >&2; exit 1 ;;
esac

# fprintd would hold the sensor while it is in use
systemctl stop fprintd 2>/dev/null || true

cd "$root/flash"
exec python3 -B collect_dac.py "${plan[@]}"

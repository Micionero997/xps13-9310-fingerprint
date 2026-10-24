#!/bin/bash
# Reliability test through fprintd, with the print enrolled in Settings: the
# same path as the lock screen and sudo. Repeats fprintd-verify and logs the
# result of every attempt, then prints the acceptance rate.
#
#   bash tools/verify-test.sh genuine 30    # the enrolled finger
#   bash tools/verify-test.sh impostor 30   # any other finger
#
# FINGER selects the enrolled finger (default right-index-finger). No root
# needed. Results go to verify-<label>-<time>.txt in the current directory.
set -euo pipefail

label="${1:?usage: verify-test.sh genuine|impostor [attempts]}"
attempts="${2:-30}"
finger="${FINGER:-right-index-finger}"
log="verify-$label-$(date +%Y%m%d-%H%M%S).txt"
matches=0

echo "Testing '$label' against $finger, $attempts attempts. Log: $log"
for i in $(seq 1 "$attempts"); do
  read -r -p "[$i/$attempts] Press Enter, then touch the sensor once... " _
  result=$( (fprintd-verify -f "$finger" 2>&1 || true) |
             (grep -oE 'Verify result: [a-z-]+' || true) | tail -1 | cut -d' ' -f3)
  result="${result:-error}"
  [ "$result" = verify-match ] && matches=$((matches + 1))
  echo "$(date +%T) $i $result" | tee -a "$log"
done

echo
echo "$label: $matches/$attempts accepted ($((100 * matches / attempts))%)" |
  tee -a "$log"

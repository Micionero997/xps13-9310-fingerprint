#!/bin/bash
# Undo install-fprintd.sh: fprintd goes back to the system libfprint.
# Enrolled prints in /var/lib/fprint are kept; remove them with
# fprintd-delete <user> before uninstalling if you no longer want them.
#
# Run with sudo: sudo bash scripts/uninstall-fprintd.sh
set -euo pipefail

rm -f /etc/systemd/system/fprintd.service.d/goodix53xd.conf
rmdir --ignore-fail-on-non-empty /etc/systemd/system/fprintd.service.d 2>/dev/null || true
rm -rf /usr/local/lib/goodix53xd /var/lib/fprint/goodix53xd-dump

systemctl daemon-reload
systemctl restart fprintd || true

echo "fprintd restored to the system libfprint"

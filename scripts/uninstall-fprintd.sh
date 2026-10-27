#!/bin/bash
# Undo install-fprintd.sh: fprintd goes back to the system libfprint.
# Enrolled prints in /var/lib/fprint are kept; remove them with
# fprintd-delete <user> before uninstalling if you no longer want them.
#
# Run with sudo: sudo bash scripts/uninstall-fprintd.sh
set -euo pipefail

# Put the lock screen back on the system pam_fprintd before removing ours
gdm_pam=/etc/pam.d/gdm-fingerprint
if [ -e "$gdm_pam.goodix53xd-orig" ]; then
  mv "$gdm_pam.goodix53xd-orig" "$gdm_pam"
elif [ -f "$gdm_pam" ]; then
  sed -i -E 's|/usr/local/lib/goodix53xd/pam_fprintd\.so max-tries=3( timeout=-1)?$|pam_fprintd.so|' "$gdm_pam"
fi

rm -f /etc/systemd/system/fprintd.service.d/goodix53xd.conf
rmdir --ignore-fail-on-non-empty /etc/systemd/system/fprintd.service.d 2>/dev/null || true
rm -rf /usr/local/lib/goodix53xd /var/lib/fprint/goodix53xd-dump

systemctl daemon-reload
systemctl restart fprintd || true

echo "fprintd restored to the system libfprint"

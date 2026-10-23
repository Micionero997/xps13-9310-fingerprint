#!/bin/bash
# Make fprintd (and so GNOME Settings, GDM, lock screen) use the libfprint
# build that contains the goodixtls53xd driver. The system libfprint package
# is left untouched; undo everything with uninstall-fprintd.sh.
#
# Run with sudo: sudo bash scripts/install-fprintd.sh [--reset-prints]
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
lib="$root/work/libfprint/build/libfprint/libfprint-2.so.2.0.0"
dest=/usr/local/lib/goodix53xd
dropin_dir=/etc/systemd/system/fprintd.service.d
# Raw frames written if FP_GOODIX53XD_DUMP was ever set for fprintd while
# debugging (biometric data)
old_dump=/var/lib/fprint/goodix53xd-dump
user="${SUDO_USER:-root}"

[ -f "$lib" ] || { echo "Missing $lib: run scripts/build-libfprint.sh first" >&2; exit 1; }

install -d -m 755 "$dest"
install -m 644 "$lib" "$dest/libfprint-2.so.2"

install -d -m 755 "$dropin_dir"
cat > "$dropin_dir/goodix53xd.conf" <<EOF
# Added by xps13-9310-fingerprint/scripts/install-fprintd.sh
[Service]
Environment=LD_LIBRARY_PATH=$dest
EOF

rm -rf "$old_dump"

systemctl daemon-reload
systemctl restart fprintd

# Prints enrolled with a build that processed images differently do not match
# this one: pass --reset-prints to remove them and enroll again.
if [ "${1:-}" = "--reset-prints" ]; then
  fprintd-delete "$user" || true
fi

echo
echo "fprintd now uses $dest/libfprint-2.so.2"
fprintd-list "$user" || true

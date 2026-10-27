#!/bin/bash
# Make fprintd (and so GNOME Settings, GDM, lock screen) use the libfprint
# build that contains the goodixtls53xd driver. The system libfprint package
# is left untouched; undo everything with uninstall-fprintd.sh.
#
# Run with sudo: sudo bash scripts/install-fprintd.sh [--reset-prints]
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
lib="$root/work/libfprint/build/libfprint/libfprint-2.so.2.0.0"
pam_module="$root/work/pam/pam_fprintd.so"
dest=/usr/local/lib/goodix53xd
gdm_pam=/etc/pam.d/gdm-fingerprint
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

# Lock screen: use pam_fprintd with the claim retry (build-pam-fprintd.sh),
# so a busy device on resume does not drop fingerprint from the unlock
# prompt. Three tries, the fprintd default, written out. No timeout: when it
# expires GDM drops fingerprint until the next lock, and the password field
# works in parallel anyway. Also updates a line from an earlier install.
if [ -f "$pam_module" ] && [ -f "$gdm_pam" ]; then
  install -m 644 "$pam_module" "$dest/pam_fprintd.so"
  [ -e "$gdm_pam.goodix53xd-orig" ] || cp -p "$gdm_pam" "$gdm_pam.goodix53xd-orig"
  sed -i -E "s#^(auth[[:space:]]+required[[:space:]]+)(pam_fprintd|$dest/pam_fprintd)\.so.*\$#\1$dest/pam_fprintd.so max-tries=3 timeout=-1#" "$gdm_pam"
  grep -q "^auth.*$dest/pam_fprintd.so" "$gdm_pam" ||
    echo "warning: no 'auth required pam_fprintd.so' line in $gdm_pam, left unchanged" >&2
else
  echo "note: $pam_module not built, lock screen keeps the system pam_fprintd" >&2
fi

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

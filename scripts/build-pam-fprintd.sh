#!/bin/bash
# Build pam_fprintd from fprintd v1.94.5 (the version Ubuntu 26.10 ships)
# with patches/pam_fprintd-claim-retry.patch, into work/pam/pam_fprintd.so.
# Only the PAM module is built; the system fprintd daemon is not replaced.
# No root needed.
#
# Usage: bash scripts/build-pam-fprintd.sh
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
# fprintd tag v1.94.5
fprintd_commit=b54a007ccf58ac0ae074c7151b223f35cbd17306
src="$root/work/fprintd"
out="$root/work/pam"

rm -rf "$src" "$out"
mkdir -p "$src" "$out"
curl -fsSL "https://gitlab.freedesktop.org/libfprint/fprintd/-/archive/$fprintd_commit/fprintd-$fprintd_commit.tar.gz" |
  tar xz -C "$src" --strip-components=1

cd "$src"
patch -p1 --quiet < "$root/patches/pam_fprintd-claim-retry.patch"

# PAM headers come from libpam0g-dev. If it is not installed, unpack its
# .deb locally instead of asking for root.
pam_cflags=()
if [ ! -f /usr/include/security/pam_modules.h ]; then
  mkdir -p "$out/pamdev"
  (cd "$out/pamdev" && apt-get download libpam0g-dev >/dev/null &&
    dpkg -x libpam0g-dev_*.deb root)
  pam_cflags=(-I "$out/pamdev/root/usr/include")
fi

echo '#define GETTEXT_PACKAGE "fprintd"' > "$out/config.h"

# Same flags as fprintd's pam/meson.build. Messages keep using the system
# fprintd translations.
gcc -O2 -g -Wall -fPIC -shared -D_FORTIFY_SOURCE=2 \
  -I "$out" -I "$src" "${pam_cflags[@]}" \
  -DLOCALEDIR='"/usr/share/locale"' \
  pam/pam_fprintd.c -o "$out/pam_fprintd.so" \
  $(pkg-config --cflags --libs libsystemd) \
  /usr/lib/x86_64-linux-gnu/libpam.so.0 \
  -Wl,--version-script,pam/pam_fprintd.ver \
  -Wl,--unresolved-symbols=report-all

echo
echo "Built $out/pam_fprintd.so"
echo "Next: sudo bash scripts/install-fprintd.sh"

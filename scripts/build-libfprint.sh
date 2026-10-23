#!/bin/bash
# Download the goodix-fp-linux-dev libfprint fork at a pinned commit, apply
# patches/libfprint-goodixtls53xd.patch (goodixtls53xd driver + SIGFM) and
# build it into work/libfprint. No root needed.
#
# Usage: bash scripts/build-libfprint.sh
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
# goodix-fp-linux-dev/libfprint, branch goodixtls (libfprint 1.94.5)
libfprint_commit=c343b6934e40dcd40a5f9e3095810d98f1175a4d
src="$root/work/libfprint"

rm -rf "$src"
mkdir -p "$src"
curl -fsSL "https://codeload.github.com/goodix-fp-linux-dev/libfprint/tar.gz/$libfprint_commit" |
  tar xz -C "$src" --strip-components=1

cd "$src"
patch -p1 --quiet < "$root/patches/libfprint-goodixtls53xd.patch"

meson setup build \
  -Ddrivers=goodixtls53xd \
  -Dintrospection=false -Ddoc=false \
  -Dudev_rules=disabled -Dudev_hwdb=disabled
ninja -C build

echo
echo "Built $src/build/libfprint/libfprint-2.so.2.0.0"
echo "Next: sudo bash scripts/install-fprintd.sh"

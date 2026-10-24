#!/bin/bash
# Install the Ubuntu packages needed to flash the sensor and build libfprint
# and pam_fprintd.
# Only the OpenCV modules SIGFM needs are installed (libopencv-dev would pull
# in every module).
#
# Run with sudo: sudo bash scripts/install-deps.sh
set -euo pipefail

apt-get install -y --no-install-recommends \
  curl patch openssl python3-usb \
  build-essential meson ninja-build pkg-config \
  libglib2.0-dev libgusb-dev libgudev-1.0-dev libpixman-1-dev libnss3-dev \
  libssl-dev libcairo2-dev libsystemd-dev libpam0g-dev \
  libopencv-core-dev libopencv-features2d-dev

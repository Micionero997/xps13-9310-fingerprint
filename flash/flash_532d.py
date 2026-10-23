#!/usr/bin/env python3
"""Guided PSK reflash of the Goodix 27c6:532d fingerprint sensor.

Same steps as goodix-fp-dump's driver_53xd.main(), with extra checks:
firmware file hash, explicit confirmation before erasing, IAP version check
before writing anything, reconnection if the sensor re-enumerates. Re-running
it resumes from whatever state the sensor is in.

Run through ../scripts/flash-sensor.sh, or from this directory as root:
  sudo python3 flash_532d.py [--dry-run]
"""
import hashlib
import re
import sys
import time

import usb.core

import compat_532d  # noqa: F401  (applies runtime patches)
import driver_53xd as d

PRODUCT = 0x532D
DRY_RUN = "--dry-run" in sys.argv
FIRMWARE_SHA256 = (
    "0f28f8f52860afea86bd56d869cd7f4fe41ba943edd1d56100113e94ecfd6c0d")


def step(text):
    print(f"\n=== {text} ===", flush=True)


def confirm(text):
    if input(f"{text}\nType YES to continue: ").strip() != "YES":
        print("Aborted, nothing changed in this step.")
        sys.exit(1)


def connect(timeout=30):
    deadline = time.time() + timeout
    while True:
        try:
            return d.init_device(PRODUCT)
        except (TimeoutError, usb.core.USBError) as error:
            if time.time() > deadline:
                raise SystemExit(f"Sensor not reachable: {error}")
            time.sleep(1)


def state(device):
    """Return (device, firmware, valid_psk), reconnecting if needed."""
    for _ in range(2):
        try:
            return device, device.firmware_version(), d.check_psk(device)
        except usb.core.USBError as error:
            print(f"USB error ({error}), reconnecting...")
            time.sleep(1)
            device = connect()
    raise SystemExit("The sensor does not answer after reconnecting.")


def main():
    step("Checking firmware file")
    with open(f"firmware/53xd/{d.TARGET_FIRMWARE}.bin", "rb") as file:
        digest = hashlib.sha256(file.read()).hexdigest()
    if digest != FIRMWARE_SHA256:
        raise SystemExit(f"Unexpected firmware hash: {digest}")
    print(f"{d.TARGET_FIRMWARE}.bin: hash ok")

    step("Current state")
    device, firmware, valid_psk = state(connect())
    print(f"Firmware: {firmware}  known PSK: {valid_psk}")

    if DRY_RUN:
        print("--dry-run: stopping here, nothing changed.")
        return

    if re.fullmatch(d.VALID_FIRMWARE, firmware):
        if firmware == d.TARGET_FIRMWARE and valid_psk:
            print("The sensor already has the known PSK: nothing to do.")
            return
        confirm("The sensor application will now be erased (only the IAP "
                "bootloader stays until the firmware is written back).")
        step("Erasing application")
        d.erase_firmware(device)
        time.sleep(1)
        device, firmware, valid_psk = state(device)
        print(f"Firmware: {firmware}  known PSK: {valid_psk}")
    elif not re.fullmatch(d.IAP_FIRMWARE, firmware):
        raise SystemExit(f"Unknown firmware '{firmware}': stopping, nothing "
                         "changed. This tool only supports "
                         f"{d.TARGET_FIRMWARE}.")

    if not re.fullmatch(d.IAP_FIRMWARE, firmware):
        raise SystemExit(f"Unexpected state '{firmware}' after erasing: "
                         "run the script again.")

    step("IAP bootloader detected")
    if not valid_psk:
        step("Writing known PSK")
        if not d.write_psk(device):
            raise SystemExit("PSK write failed. The sensor is in IAP mode: "
                             "run the script again.")
        print("PSK written and verified.")

    step("Writing firmware")
    d.update_firmware(device)

    step("Reconnecting after flash")
    device, firmware, valid_psk = state(connect())
    print(f"Firmware: {firmware}  known PSK: {valid_psk}")
    if firmware != d.TARGET_FIRMWARE or not valid_psk:
        raise SystemExit("Unexpected state after flashing: run the script "
                         "again, it resumes from the right step.")

    step("Done: the sensor now uses the known PSK")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Guided collection of raw frames at several DAC bases per touch.

At the driver's DAC base (0x10c) a pressed finger drives ~17% of the pixels
to 0, clipping the ridges. Lower bases raise the readout (~70 counts per
step), so each touch is captured at all BASES to pick one offline with
tools/sigfm-eval.

Writes frame + background pairs (64x80 u16, the format tools/ expect) to
../dump-dac/<session>/. Biometric data: delete it when done.

Needs the PSK reflash done by flash_532d.py. Writes no firmware.
Run through ../tools/collect-dac.sh, or from this directory as root:
  sudo python3 collect_dac.py right-index:16 right-middle:8 ...
"""
import os
import socket
import statistics
import struct
import subprocess
import sys
import time

import compat_532d  # noqa: F401  (applies runtime patches)
import driver_53xd as d
import goodix
import tool

PRODUCT = 0x532D
BASES = [0x10C, 0x100, 0xF4, 0xE8, 0xDC]
LIFT_BASE = 0x10C
EMPTY_MEDIAN = 3000  # at LIFT_BASE an empty sensor reads ~3640
SETTLE_S = 0.5  # FDT fires on first contact; let the finger press down
LIFT_TIMEOUT_S = 20

FDT_MODE = b"\x0d\x01\x28\x01\x22\x01\x28\x01\x24\x01" + b"\x00" * 16
FDT_DOWN = (b"\x8c\x01\x28\x01\x22\x01\x28\x01\x24\x01"
            b"\x91\x91\x8b\x8b\x96\x96\x91\x91\x98\x98\x90\x90\x92\x92\x88\x88")

# goodix.py prints every call; keep the terminal for the user's prompts
OUT = sys.__stdout__


def say(*args):
    print(*args, file=OUT, flush=True)


def wait_enter(prompt):
    say(prompt)
    sys.stdin.readline()


def grab(device, tls_client, tls_server, base):
    device.write_sensor_register(0x022C, b"\x0a\x03")
    request = struct.pack("<BBHHHH", 0x01, 0x03, base, base - 6, base,
                          base - 4)
    tls_client.sendall(
        device.mcu_get_image(request,
                             goodix.FLAGS_TRANSPORT_LAYER_SECURITY_DATA)[9:])
    raw = tls_server.stdout.read(7684)
    device.write_sensor_register(0x022C, b"\x0a\x02")
    return tool.decode_image(raw[:-4])


def arm_finger_down(device):
    device.mcu_switch_to_fdt_mode(FDT_MODE + b"\x00", False)
    device.mcu_switch_to_fdt_mode(FDT_MODE + b"\x01", True)
    device.mcu_switch_to_sleep_mode()
    device.query_mcu_state(b"\x01\x01\x01", False)
    device.mcu_switch_to_fdt_down(FDT_DOWN + b"\x00", False)


def connect_tls(device, tls_server):
    for _ in range(50):
        try:
            client = socket.create_connection(("localhost", 4433))
            break
        except ConnectionRefusedError:
            time.sleep(0.1)
    else:
        raise SystemExit("openssl s_server did not start")
    tool.connect_device(device, client)
    return client


def save(path, frame, background):
    with open(path, "wb") as file:
        file.write(struct.pack(f"<{2 * len(frame)}H", *frame, *background))


def main():
    plan = [(arg.split(":")[0], int(arg.split(":")[1])) for arg in sys.argv[1:]]
    if not plan:
        raise SystemExit(__doc__)

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "dump-dac", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(root)
    sys.stdout = open(os.devnull, "w")

    device = d.init_device(PRODUCT)
    if device.firmware_version() != d.TARGET_FIRMWARE or not d.check_psk(device):
        raise SystemExit("Sensor not reflashed: run flash_532d.py first")

    tls_server = subprocess.Popen([
        "openssl", "s_server", "-nocert", "-psk", d.PSK.hex(), "-port",
        "4433", "-quiet"
    ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        if not device.reset(True, False, 20)[0]:
            raise ValueError("Reset failed")
        tls_client = connect_tls(device, tls_server)
        try:
            if not device.upload_config_mcu(d.DEVICE_CONFIG):
                raise ValueError("Failed to upload config")
            device.mcu_switch_to_fdt_mode(FDT_MODE + b"\x00", False)
            device.mcu_switch_to_fdt_mode(FDT_MODE + b"\x01", True)

            for label, touches in plan:
                wait_enter(f"\n=== {label}: {touches} touches. "
                           "Press Enter when ready (sensor clear).")
                for i in range(1, touches + 1):
                    backgrounds = {b: grab(device, tls_client, tls_server, b)
                                   for b in BASES}
                    if statistics.median(backgrounds[LIFT_BASE]) < EMPTY_MEDIAN:
                        say("  lift your finger off the sensor...")
                        while statistics.median(grab(device, tls_client,
                                                     tls_server,
                                                     LIFT_BASE)) < EMPTY_MEDIAN:
                            time.sleep(0.1)
                        backgrounds = {b: grab(device, tls_client, tls_server, b)
                                       for b in BASES}

                    arm_finger_down(device)
                    say(f"[{label} {i}/{touches}] place your finger and hold it still")
                    device.mcu_switch_to_fdt_down(FDT_DOWN + b"\x01", True)
                    time.sleep(SETTLE_S)
                    frames = {b: grab(device, tls_client, tls_server, b)
                              for b in BASES}
                    say("  ok, lift your finger")

                    for b in BASES:
                        save(os.path.join(root, f"{label}-{i:02d}-{b:03x}.bin"),
                             frames[b], backgrounds[b])

                    deadline = time.time() + LIFT_TIMEOUT_S
                    while (statistics.median(grab(device, tls_client, tls_server,
                                                  LIFT_BASE)) < EMPTY_MEDIAN
                           and time.time() < deadline):
                        time.sleep(0.1)
        finally:
            tls_client.close()
    finally:
        tls_server.terminate()

    owner = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if all(owner):
        for dirpath, _, files in os.walk(os.path.join(root, "..")):
            os.chown(dirpath, int(owner[0]), int(owner[1]))
            for name in files:
                os.chown(os.path.join(dirpath, name), int(owner[0]), int(owner[1]))
    say(f"\nDone: frames saved in {os.path.abspath(root)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read-only probe for the Goodix 27c6:532d fingerprint sensor.

Sends only query commands (NOP, FIRMWARE_VERSION, PRESET_PSK_READ, READ_OTP):
no reset, erase, flash or PSK write. Packet format follows goodix-fp-dump
(github.com/goodix-fp-linux-dev/goodix-fp-dump).

Run as root:  sudo python3 -I probe.py
"""
import ctypes
import struct
import sys

VID, PID = 0x27C6, 0x532D
EP_OUT, EP_IN = 0x01, 0x83
IFACE = 0

CMD_NOP = 0x00
CMD_ACK = 0xB0
CMD_READ_OTP = 0xA6
CMD_FIRMWARE_VERSION = 0xA8
CMD_PRESET_PSK_READ = 0xE4

FLAGS_MP = 0xA0

# Hash of the PMK written by the goodix-fp-dump custom firmware (all-zero PSK).
# If the sensor reports this, it was already reflashed by that project.
ZERO_PSK_PMK_HASH = bytes.fromhex(
    "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925")

LIBUSB_ERROR_TIMEOUT = -7


class USB:

    def __init__(self):
        self.lib = ctypes.CDLL("libusb-1.0.so.0")
        self.lib.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        self.lib.libusb_open_device_with_vid_pid.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16
        ]
        for name in ("libusb_claim_interface", "libusb_release_interface",
                     "libusb_kernel_driver_active",
                     "libusb_detach_kernel_driver"):
            getattr(self.lib, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.libusb_bulk_transfer.argtypes = [
            ctypes.c_void_p, ctypes.c_ubyte,
            ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.c_uint
        ]
        self.lib.libusb_close.argtypes = [ctypes.c_void_p]
        self.lib.libusb_error_name.restype = ctypes.c_char_p

        self.ctx = ctypes.c_void_p()
        self._check(self.lib.libusb_init(ctypes.byref(self.ctx)), "init")
        self.handle = self.lib.libusb_open_device_with_vid_pid(
            self.ctx, VID, PID)
        if not self.handle:
            raise SystemExit(
                "Cannot open 27c6:532d (not found or no permission: run with sudo)")
        if self.lib.libusb_kernel_driver_active(self.handle, IFACE) == 1:
            self.lib.libusb_detach_kernel_driver(self.handle, IFACE)
        self._check(self.lib.libusb_claim_interface(self.handle, IFACE),
                    "claim_interface")

    def _check(self, rc, what):
        if rc < 0:
            raise OSError(f"libusb {what}: {self.lib.libusb_error_name(rc).decode()}")

    def write(self, data: bytes, timeout_ms=2000):
        if len(data) % 64:
            data += b"\x00" * (64 - len(data) % 64)
        for i in range(0, len(data), 64):
            chunk = data[i:i + 64]
            n = ctypes.c_int()
            self._check(
                self.lib.libusb_bulk_transfer(self.handle, EP_OUT, chunk,
                                              len(chunk), ctypes.byref(n),
                                              timeout_ms), "write")

    def read(self, size=0x10000, timeout_ms=2000):
        buf = ctypes.create_string_buffer(size)
        n = ctypes.c_int()
        rc = self.lib.libusb_bulk_transfer(self.handle, EP_IN, buf, size,
                                           ctypes.byref(n), timeout_ms)
        if rc == LIBUSB_ERROR_TIMEOUT and n.value == 0:
            return None
        self._check(rc, "read")
        return buf.raw[:n.value]

    def close(self):
        self.lib.libusb_release_interface(self.handle, IFACE)
        self.lib.libusb_close(self.handle)
        self.lib.libusb_exit(self.ctx)


def message_pack(payload: bytes, flags=FLAGS_MP) -> bytes:
    head = struct.pack("<BH", flags, len(payload))
    return head + bytes([sum(head) & 0xFF]) + payload


def message_protocol(payload: bytes, command: int, checksum=True) -> bytes:
    data = struct.pack("<BH", command, len(payload) + 1) + payload
    return data + bytes([(0xAA - sum(data)) & 0xFF if checksum else 0x88])


def parse(data: bytes):
    """Return (command, payload) from a message pack + message protocol frame."""
    if data is None or len(data) < 7:
        raise ValueError(f"short reply: {data!r}")
    flags, length, csum = data[0], struct.unpack("<H", data[1:3])[0], data[3]
    if sum(data[0:3]) & 0xFF != csum:
        raise ValueError(f"bad pack checksum: {data[:16].hex()}")
    if flags != FLAGS_MP:
        raise ValueError(f"unexpected flags 0x{flags:02x}")
    body = data[4:4 + length]
    cmd, plen = body[0], struct.unpack("<H", body[1:3])[0]
    return cmd, body[3:2 + plen]


def request(usb: USB, command: int, payload: bytes):
    usb.write(message_pack(message_protocol(payload, command)))
    cmd, ack = parse(usb.read())
    if cmd != CMD_ACK or ack[0] != command:
        raise ValueError(f"expected ACK for 0x{command:02x}, got 0x{cmd:02x} {ack.hex()}")
    cmd, reply = parse(usb.read())
    if cmd != command:
        raise ValueError(f"expected reply 0x{command:02x}, got 0x{cmd:02x}")
    return reply


def main():
    usb = USB()
    try:
        # Drain anything left in the device's reply buffer.
        while usb.read(timeout_ms=100):
            pass

        usb.write(message_pack(message_protocol(b"\x00" * 4, CMD_NOP, checksum=False)))
        usb.read(timeout_ms=100)
        print("NOP: ok")

        fw = request(usb, CMD_FIRMWARE_VERSION, b"\x00\x00")
        fw = fw.split(b"\x00")[0].decode(errors="replace")
        print(f"Firmware: {fw}")

        psk = request(usb, CMD_PRESET_PSK_READ,
                      struct.pack("<IIII", len(ZERO_PSK_PMK_HASH), 0,
                                  0xBB020001, 0))
        if psk[0] != 0x00:
            print(f"PSK read: status 0x{psk[0]:02x} (no PSK hash available)")
        else:
            flags, length = struct.unpack("<II", psk[1:9])
            pmk_hash = psk[9:9 + length]
            print(f"PSK flags: 0x{flags:08x}")
            print(f"PMK hash:  {pmk_hash.hex()}")
            print("PMK hash matches goodix-fp-dump zero PSK:",
                  pmk_hash == ZERO_PSK_PMK_HASH)

        otp = request(usb, CMD_READ_OTP, b"\x00\x00")
        print(f"OTP ({len(otp)} bytes): {otp.hex()}")
    finally:
        usb.close()


if __name__ == "__main__":
    sys.exit(main())

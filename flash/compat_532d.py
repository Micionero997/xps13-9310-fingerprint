"""Runtime patches needed to drive the 27c6:532d with goodix-fp-dump.

Set GOODIX_LOG_IO=1 to log raw USB traffic.
"""
import os

import usb.core

import protocol


def _log_io(cls):
    """Log raw USB traffic (truncated) to debug protocol mismatches."""
    write, read = cls.write, cls.read

    def logged_write(self, data, timeout=5):
        print(f"  >> {data[:32].hex()}{'...' if len(data) > 32 else ''}")
        return write(self, data, timeout)

    def logged_read(self, size=0x10000, timeout=5):
        data = read(self, size, timeout)
        print(f"  << {data[:32].hex()}{'...' if len(data) > 32 else ''}")
        return data

    cls.write, cls.read = logged_write, logged_read


if os.environ.get("GOODIX_LOG_IO"):
    _log_io(protocol.USBProtocol)

# protocol.USBProtocol calls set_configuration() on every connect. The 532d
# is already configured by the kernel; with that request the sensor was seen
# replying without the ACK frame goodix.py requires (suspected cause). Skip it.
usb.core.Device.set_configuration = lambda self, configuration=None: None

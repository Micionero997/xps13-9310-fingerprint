# Fingerprint reader on the Dell XPS 13 9310 2-in-1 (Goodix 27c6:532d) on Ubuntu

The Goodix `27c6:532d` reader in the XPS 13 9310 2-in-1 has no Linux driver.
This repository makes it work with fprintd, so you can unlock the screen and
log in with your fingerprint from GNOME. It provides:

- a **libfprint driver** (`goodixtls53xd`) built on the
  [goodix-fp-linux-dev libfprint fork](https://github.com/goodix-fp-linux-dev/libfprint),
  with the SIGFM matcher;
- a **guided flasher** that puts a known TLS key on the sensor, based on
  [goodix-fp-dump](https://github.com/goodix-fp-linux-dev/goodix-fp-dump);
- install and uninstall scripts for **fprintd**. The system libfprint package
  is not replaced.

Tested on one XPS 13 9310 2-in-1 with Ubuntu 26.10 and GNOME.

## Read this first

- **Flashing is irreversible.** The sensor's factory TLS key is replaced with a
  publicly known one. The original key cannot be restored, and the Windows
  fingerprint driver will not work with the sensor afterwards. If you dual-boot
  and use Windows Hello, stop here.
- **It can brick the sensor.** The flasher erases the sensor application and
  writes it back. If that is interrupted, the sensor stays in bootloader mode.
  Running the flasher again normally resumes from there, but there is no
  guarantee. Do not suspend or unplug the laptop while it runs.
- **The sensor is tiny (64×80 pixels) and matching is weak.** In our tests
  about **1 in 2** touches of the enrolled finger was accepted, so expect to
  touch again sometimes. No touch of another finger was accepted (24 tries,
  best score 3 against a threshold of 10). That is a small test on one person.
  Use the fingerprint as a convenience for unlocking, not as strong security.
  Your password keeps working everywhere. On a default Ubuntu install `sudo`
  does not use the fingerprint.
- Unofficial and unsupported by Dell, Goodix or libfprint. Use at your own risk.

## Requirements

Check that you have this exact sensor:

```bash
lsusb -d 27c6:532d
```

It must print `Shenzhen Goodix Technology Co.,Ltd. Fingerprint`. The flasher
checks the firmware version too: only `GF5298_GM168SEC_APP_13016` is
supported. Anything else stops it before any change.

## Install

From a clone of this repository:

```bash
sudo bash scripts/install-deps.sh
```

Optional: read-only check of the sensor state (firmware version, whether it
already has the known key):

```bash
sudo bash scripts/flash-sensor.sh --dry-run
```

Flash the sensor. It asks you to type `YES` before erasing anything:

```bash
sudo bash scripts/flash-sensor.sh
```

Build libfprint with the driver (no root):

```bash
bash scripts/build-libfprint.sh
```

Make fprintd use it:

```bash
sudo bash scripts/install-fprintd.sh
```

Then open **Settings → System → Users → Fingerprint Login** and enroll a
finger. Move the finger a little between touches: the sensor is small, so
covering different areas matters for later matches. Lock the screen
(Super+L) and unlock with that finger.

**The first login after boot always asks for the password.** This is how
GNOME works, not a driver problem. GNOME Shell offers the fingerprint only to
unlock a session that is already running: the lock screen, after suspend, or
after closing the lid. The first login needs the password to unlock the GNOME
keyring (saved Wi-Fi, browser and app passwords). At that point the login
screen does not query fprintd at all, so the reader stays silent.

## Uninstall

```bash
sudo bash scripts/uninstall-fprintd.sh
```

fprintd goes back to the system libfprint. Remove enrolled prints from
Settings first if you no longer want them. The sensor keeps the known key.

## Troubleshooting

- No fingerprint prompt on the login screen right after boot: expected, see
  [Install](#install). Lock the screen and the fingerprint works.
- `fprintd-list $USER` should show "Goodix TLS Fingerprint Sensor 53xd".
- `journalctl -u fprintd -b` shows driver errors.
- To see the matcher scores, run a libfprint example with debug output:
  `sudo G_MESSAGES_DEBUG=all work/libfprint/build/examples/verify`. That
  needs a print enrolled with `work/libfprint/build/examples/enroll`, not with
  Settings.
- After rebuilding with different image processing, reinstall with
  `--reset-prints` and enroll again.

## How it works

See [docs/NOTES.md](docs/NOTES.md) for the protocol quirks and the
measurements behind the settings, and [tools/README.md](tools/README.md) to
re-tune the matcher on your own unit.

In short:

- `flash/` reflashes the sensor with goodix-fp-dump's all-zero PSK. The
  firmware (`GF5298_GM168SEC_APP_13016`) is downloaded from
  [goodix-firmware](https://github.com/goodix-fp-linux-dev/goodix-firmware)
  at a pinned commit and checked against its SHA-256.
- `patches/libfprint-goodixtls53xd.patch` applies to the fork's `goodixtls`
  branch at commit `c343b69`. It adds:
  - the `goodixtls53xd` driver;
  - fixes to the shared goodixtls code (0xb2 packets, stale-input resync,
    optional TLS-established command);
  - SIGFM from the fork's `sigfm` branch, with a match-ordering fix;
  - a core timeout fix.
- `scripts/install-fprintd.sh` copies the built `libfprint-2.so.2` to
  `/usr/local/lib/goodix53xd` and adds a systemd drop-in so that only fprintd
  loads it.

## Credits

- [goodix-fp-linux-dev](https://github.com/goodix-fp-linux-dev): goodix-fp-dump,
  the goodixtls libfprint fork and SIGFM (Matthieu Charette, Natasha
  England-Elbro, Alexander Meiler, Timur Mangliev and contributors).
- [libfprint](https://fprint.freedesktop.org/).

## License

- `patches/` modifies libfprint: LGPL-2.1-or-later, like libfprint.
- `flash/goodix.py`, `protocol.py`, `tool.py`, `driver_53xd.py` are unmodified
  copies from goodix-fp-dump (MIT, see `flash/LICENSE.goodix-fp-dump`).
- Everything else in this repository: MIT, see [LICENSE](LICENSE).

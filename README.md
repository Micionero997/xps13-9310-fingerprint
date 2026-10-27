# Fingerprint reader on the Dell XPS 13 9310 2-in-1 (Goodix 27c6:532d) on Ubuntu

The Goodix `27c6:532d` reader in the XPS 13 9310 2-in-1 has no Linux driver.
This repository makes it work with fprintd, so you can unlock the GNOME lock
screen with your fingerprint. Read the warning below on how weak the matching
is. It provides:

- a **libfprint driver** (`goodixtls53xd`) built on the
  [goodix-fp-linux-dev libfprint fork](https://github.com/goodix-fp-linux-dev/libfprint),
  with the SIGFM matcher;
- a **guided flasher** that puts a known TLS key on the sensor, based on
  [goodix-fp-dump](https://github.com/goodix-fp-linux-dev/goodix-fp-dump);
- install and uninstall scripts for **fprintd**. The system libfprint package
  is not replaced.

Tested on one XPS 13 9310 2-in-1 with Ubuntu 26.10 and GNOME.

> [!WARNING]
> **This reader does not tell fingers apart reliably.** The test ran through
> fprintd with a print enrolled in GNOME Settings, on one unit and one person.
> The enrolled finger was accepted in **19 of 30** touches (63%). Touches of
> six *other* fingers were accepted in **7 of 30** (23%), with scores from 10
> to 134 against a threshold of 10. Genuine and impostor scores overlap: no
> threshold rejects the other fingers and still leaves the reader usable.
> Someone else can likely unlock your session within a few tries.
> **Do not use it for `sudo`, polkit or anything that grants privileges.**
> Treat lock-screen unlock as a convenience that gives no real protection.
> Measure your own unit with `tools/verify-test.sh` (see
> [tools/README.md](tools/README.md)).

## Read this first

- **Flashing replaces the sensor's TLS key, and dual boot with Windows
  conflicts.** The key on the sensor was most likely written by the Windows
  Goodix driver, which keeps it inside that Windows install. The flasher
  replaces it with a publicly known key, and the old key cannot be restored.
  On similar Goodix sensors, the Windows driver pairs the sensor again with a
  new key of its own the next time Windows boots
  ([538d](https://github.com/jvsena42/dell-goodix-538d-linux/issues/7),
  [HTK32](https://www.problemofnetwork.com/posts/goodix-htk32-omarchy/)), so
  Windows Hello will probably work again. *This has not been verified on the
  532d.* After that, this Linux driver refuses the sensor (its key check
  fails) until you run the flasher again, and the next Windows boot takes the
  sensor back. A Windows
  update could also change the sensor firmware: the flasher only supports
  `GF5298_GM168SEC_APP_13016` and stops, without changes, on any other version.
  If you dual-boot and rely on Windows Hello, think twice.
- **It can brick the sensor.** The flasher erases the sensor application and
  writes it back. If that is interrupted, the sensor stays in bootloader mode.
  Running the flasher again normally resumes from there, but there is no
  guarantee. Do not suspend or unplug the laptop while it runs.
- **The sensor is tiny (64×80 pixels) and matching is weak**, both ways. About
  1 in 3 touches of your enrolled finger is rejected, and about 1 in 4 touches
  of other fingers is accepted (see the warning above). An earlier offline
  estimate, with no impostor accepted, turned out to be far too optimistic.
  Your password keeps working everywhere. On a default Ubuntu install `sudo`
  does not use the fingerprint; keep it that way.
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

Build the patched `pam_fprintd` PAM module (no root). Without it the lock
screen often drops the fingerprint after suspend; see
[How it works](#how-it-works):

```bash
bash scripts/build-pam-fprintd.sh
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
- `patches/pam_fprintd-claim-retry.patch` applies to fprintd v1.94.5. On
  resume GNOME Shell can ask for the reader while fprintd still holds it for
  the previous prompt; the stock module then gives up at once and GDM hides
  the fingerprint until the next lock. The patched module waits up to 3
  seconds for the reader instead.
- `scripts/install-fprintd.sh` copies the built `libfprint-2.so.2` (and
  `pam_fprintd.so`, if built) to `/usr/local/lib/goodix53xd`, adds a systemd
  drop-in so that only fprintd loads the library, and points the lock screen
  (`/etc/pam.d/gdm-fingerprint`) at the patched module with 3 tries and no
  timeout. With the default 30-second timeout GDM drops the fingerprint
  until the next lock; the password field works alongside it anyway. The
  original file is kept as `gdm-fingerprint.goodix53xd-orig`.

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

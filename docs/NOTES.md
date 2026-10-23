# Technical notes: Goodix 27c6:532d

Findings from bringing up the sensor of a Dell XPS 13 9310 2-in-1 on
Ubuntu 26.10. They explain the choices in `patches/` and `flash/`.

## Sensor

- USB `27c6:532d`, "Goodix FingerPrint", vendor class, bulk EP 0x01 OUT and
  0x83 IN, 64-byte packets.
- Application firmware `GF5298_GM168SEC_APP_13016`, IAP bootloader
  `MILAN_GM168SEC_IAP_10007`, the same family goodix-fp-dump calls 53xd.
- Image: 64 wide × 80 tall, 12-bit, 4 pixels packed in 6 bytes; the
  decrypted frame is 7680 bytes plus a 4-byte trailer.
- Frames are TLS-PSK encrypted. The factory PSK is unknown, so the sensor
  has to be reflashed with a known one (`flash/`).

## Protocol quirks

- **No ACK after SET_CONFIGURATION.** The sensor was seen replying to
  commands without the ACK frame goodix-fp-dump expects once pyusb's
  `set_configuration()` had been sent. `flash/compat_532d.py` skips it, and
  libfprint never sends it.
- **Image replies use pack flag 0xb2** (TLS application data) with a 9-byte
  header before the TLS record. The fork's `goodix.c` only handled 0xa0 and
  0xb0.
- **TLS_SUCCESSFULLY_ESTABLISHED (0xd4)** is not sent by goodix-fp-dump.
  On 532d its ACK arrives after ~18 ms (the fork waits 10 ms) and the next
  command is dropped, so goodixtls53xd skips it and waits 20 ms after the
  handshake instead.
- **Reset** needs payload `0x05` (sensor bits 0 and 2), the reply number is
  2048. **PSK read** uses a 16-byte payload (length, offset, flags, 0) with
  flags `0xbb020001`.
- **Stale replies.** If libfprint deactivates the device while an image
  request is in flight (end of enrollment), the sensor still sends the
  ~7.7 KB reply. On the next activation it arrived mid-packet and the fork's
  reassembly treated it as a header, swallowing every later reply (first
  command timed out). goodix.c now drops data whose pack header has an
  unknown flag or a bad checksum, and the driver flushes input for 100 ms
  before its first command.

## Image acquisition

- MCU_GET_IMAGE payload: flag `0x01`, `0x03`, then four DAC words
  `base, base-6, base, base-4`; register `0x022c` is set to `0x0a03` before
  and `0x0a02` after each frame.
- ~70 counts per DAC step. At base `0x10c` an empty sensor reads ~3640; a
  pressed finger pulls the median to 300–600 and clips ~9–17% of the pixels
  at 0. Lower bases avoid the clipping but saturate the empty sensor, which
  removes background subtraction and lets fixed-pattern noise dominate. In
  tests every lower base gave worse impostor separation, so the driver stays
  at `0x10c`.
- goodix-fp-dump's finger-frame settings (flag `0x41`, register `0x05`,
  base `0xa5`) saturate or return all zeros on this unit.
- The FDT finger-down event fires on first contact. The driver keeps
  sampling until coverage is stable, then submits the best frame.
- Lift is detected by polling frames, because no finger-up FDT payload is
  known for 53xd. A frame with median > 3000 is "empty" and becomes the new
  background. Sessions often start with the finger still on the sensor, so
  the background is never taken from activation alone.
- A ~6% set of pixels at the sensor edges always reads 0.

## Matching

- **NBIS cannot work.** Even on clean images NBIS finds 1–8 minutiae, and
  bozorth3 refuses to score below 10 (`MIN_COMPUTABLE_BOZORTH_MINUTIAE`).
- **SIGFM** (SIFT keypoints + geometric consistency, from the goodix-fp-linux-dev
  fork) is ported in. Without preprocessing SIFT finds ~18 keypoints per
  frame, below libfprint's minimum of 25. With local contrast normalization
  (z-score over a 7×7 window) and 2× bilinear upscaling it finds ~230.
- Upstream sigfm.cpp's `match::operator<` compares only `p1.y`, so distinct
  matches on the same row collapse in a `std::set`. The patch adds a full
  ordering (`SIGFM_FIX_MATCH_ORDER`, enabled), which the threshold was
  measured with.
- **Measured on one unit and one person** (16 enroll touches; 8 probe touches
  ~15 minutes later; 24 touches of 3 other fingers): impostors scored at most
  3, and 4 of 8 genuine probes scored ≥ 10 (10, 17, 95, 911). Threshold: 10.
  This is a small sample. Treat the reader as a convenience for unlocking,
  not as strong authentication.

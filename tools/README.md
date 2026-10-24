# Tuning tools

Not needed to use the fingerprint reader. They are here so that the matcher
settings in `goodix53xd.c` (DAC base, local normalization, SIGFM threshold)
can be re-measured on other units of the sensor.

All of them handle **raw fingerprint images**. Keep the dumps local; the
repository's `.gitignore` excludes `dump-dac/` and `work/`.

## Measuring real-world reliability

This is the measurement that matters. It goes through fprintd with the print
you enrolled in Settings, exactly like the lock screen:

```bash
bash tools/verify-test.sh genuine 30    # the enrolled finger, one touch each
bash tools/verify-test.sh impostor 30   # rotate through your other fingers
```

To also see the score of every comparison, enable fprintd debug logging for
the duration of the test, then remove it:

```bash
printf '[Service]\nEnvironment=G_MESSAGES_DEBUG=all\n' | sudo tee /etc/systemd/system/fprintd.service.d/debug.conf
sudo systemctl daemon-reload && sudo systemctl restart fprintd
# ... run the tests, then: journalctl -u fprintd -b | grep 'sigfm score'
sudo rm /etc/systemd/system/fprintd.service.d/debug.conf
sudo systemctl daemon-reload && sudo systemctl restart fprintd
```

Each touch is compared with every enrolled print until one reaches the
threshold. Group the logged scores by attempt using the timestamps in the
`verify-*.txt` files. See docs/NOTES.md for the results on the reference unit.
A test on 30 impostor touches cannot show a false-accept rate below about
10%; use many more before trusting a threshold.

## Collecting frames

```bash
sudo bash tools/collect-dac.sh 1   # 16 enroll touches + 3 other fingers x 8
sudo bash tools/collect-dac.sh 2   # some hours later: 8 probe touches
```

Every touch is captured at several DAC bases (0x10c ... 0xdc), each with its
own empty-sensor background, as `dump-dac/<session>/<label>-<n>-<base>.bin`
(64x80 frame, then 64x80 background, little-endian u16).

The driver can also dump what it sees at runtime: run any libfprint program
with `FP_GOODIX53XD_DUMP=<dir>` (never set it for fprintd in normal use).

## Evaluating SIGFM

Build after `scripts/build-libfprint.sh`:

```bash
SF=work/libfprint/libfprint/sigfm
g++ -std=c++17 -O2 -DSIGFM_FIX_MATCH_ORDER -I/usr/include/opencv4 -I$SF \
  -o work/sigfm-eval tools/sigfm-eval.cpp $SF/sigfm.cpp \
  -lopencv_features2d -lopencv_core
```

Each argument is `label:file`; the first argument names the template label.
For every sample it prints the best score against all template samples, which
is how libfprint verifies against a multi-print enrollment:

```bash
A=dump-dac/<session-1>; B=dump-dac/<session-2>
SCALE=2 NORM_RADIUS=3 work/sigfm-eval T \
  $(ls $A/right-index-*-10c.bin | sed 's/^/T:/') \
  $(ls $B/right-index-probe-*-10c.bin | sed 's/^/G:/') \
  $(ls $A/*-10c.bin | grep -v right-index | sed 's/^/I:/')
```

Pick a threshold above every impostor (`I`) score and check how many genuine
(`G`) probes from the other session pass it. Same-session probes score far
higher than real unlocks and must not be used to set the threshold.

`driver-image-test.c` runs the driver's own `build_image()` on a dump, to
check it stays byte-identical to `sigfm-eval.cpp` after changes.
`nbis-eval.c` is the NBIS/bozorth3 counterpart: it shows why NBIS cannot
work on this sensor (at most ~8 minutiae per image, bozorth3 needs 10).

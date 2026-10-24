# Unlocking 1Password with the fingerprint

1Password for Linux can unlock with "system authentication". It asks
**polkit** for permission, and polkit asks PAM. This page adds the fingerprint
to the polkit PAM service only, so 1Password can use it while `sudo`, `su` and
the login screen keep using the password.

> [!CAUTION]
> **This gives the weak matcher power over privileged actions.** The reader
> accepted other fingers in about 1 of 4 touches in testing (see the warning
> in the [README](../README.md)). polkit uses one PAM service, `polkit-1`, for
> every request. PAM cannot tell which application is asking, so the
> fingerprint is accepted for **all** polkit prompts, not just 1Password:
>
> - unlocking 1Password, authorizing the `op` CLI and the 1Password SSH agent;
> - **administrator prompts**: `pkexec` (a root shell), installing software,
>   changing system settings, adding users.
>
> Someone holding your laptop with the session unlocked could get root, or
> open your vault, after a few tries with any finger. Only do this if you
> accept that risk. The 1Password password and your account password keep
> working.

## Do not enable fprintd in `common-auth`

Do **not** turn on "Fingerprint authentication" in `sudo pam-auth-update`
(or run `pam-auth-update --enable fprintd`). That puts the fingerprint in
`/etc/pam.d/common-auth`, which almost every service includes: `su`, `sudo`,
console login and polkit. If you already did, turn it off: run
`sudo pam-auth-update` and unselect "Fingerprint authentication". Then check
that this prints nothing:

```bash
grep fprintd /etc/pam.d/common-auth
```

## Setup

1. Install the driver and enroll a finger as described in the
   [README](../README.md#install).

2. Add the fingerprint to the polkit PAM service. Ubuntu ships the service in
   `/usr/lib/pam.d/polkit-1`; a file with the same name in `/etc/pam.d` takes
   precedence. Copy it, then add `pam_fprintd` before `@include common-auth`:

   ```bash
   [ -e /etc/pam.d/polkit-1 ] || sudo cp /usr/lib/pam.d/polkit-1 /etc/pam.d/polkit-1
   sudo sed -i '/^@include common-auth/i auth sufficient pam_fprintd.so max-tries=1 timeout=10' /etc/pam.d/polkit-1
   ```

   On Ubuntu 26.10 the result is:

   ```
   #%PAM-1.0

   auth sufficient pam_fprintd.so max-tries=1 timeout=10
   @include common-auth
   @include common-account
   @include common-password
   session       required   pam_env.so readenv=1 user_readenv=0
   @include common-session-noninteractive
   ```

   With `max-tries=1 timeout=10`, a rejected touch or 10 seconds without one
   falls back to the password.

3. Check that polkit asks for the fingerprint. GNOME should show an
   authentication dialog that asks you to touch the reader:

   ```bash
   pkexec true
   ```

4. In 1Password open **Settings → Security** and turn on
   **Unlock using system authentication**. Lock 1Password and unlock it
   again: it should ask for the fingerprint.

The first unlock after 1Password starts (for example after boot) always asks
for the 1Password password. This is a 1Password rule, not a driver problem.

## Undo

```bash
sudo rm /etc/pam.d/polkit-1
```

polkit goes back to the system file in `/usr/lib/pam.d` and asks for the
password again. You can also turn off **Unlock using system authentication**
in 1Password.

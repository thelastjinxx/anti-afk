r"""
Minecraft Bedrock (Android) anti-AFK helper - RUN FROM PHONE (Termux)
-------------------------------------------
Sends random touch inputs through ADB so your character isn't idle.
Android only. This file contains the setup guide for: RUN FROM PHONE (Termux).

WHAT IT DOES
  Picks a random action (jump, walk a few steps and back, look around,
  sneak, swing, switch hotbar slot) at randomized times. Action choice is
  weighted and never repeats back-to-back, gaps between actions vary
  (including quick follow-ups and occasional long pauses), and sometimes it
  chains 2-3 actions together. Tweak the settings below to taste.

NOTE ON PLACEHOLDERS
  In commands, <IP>, <port> etc. are placeholders. Replace the whole thing,
  including the < > brackets, with the real value (e.g. 192.168.1.5:41233).


=====================================================================
SETUP: RUN IT FROM THE PHONE ITSELF (Termux, no computer or cable)
=====================================================================
Needs Android 11 or later and a Wi-Fi connection (no internet required).

  1. Install Termux from F-DROID (the Play Store version is outdated and
     breaks).
  2. Save this script to your phone's Downloads folder.
  3. In Termux, install Python and ADB. Run it as ONE command with -y,
     otherwise the confirmation prompt can abort:
         pkg install -y python android-tools
  4. Copy the script into Termux (tap Allow on the permission prompt):
         termux-setup-storage
         cp ~/storage/downloads/minecraft_antiafk_phone.py ~/
     Check with `ls`.
  5. Make sure ADB works:
         adb version
     If you get "CANNOT LINK EXECUTABLE" or "cannot locate symbol", the
     packages are out of date or the mirror is stale. Run:
         termux-change-repo        (pick a different mirror, press OK)
         pkg clean
         pkg update
         pkg upgrade -y
         pkg install -y libc++ android-tools
         adb version
  6. Connect to Wi-Fi, then go to Settings > Developer options and turn on
     "Wireless debugging". (Developer options is unlocked by tapping
     "Build number" 7 times in Settings > About phone.)
  7. Pair Termux with the phone. Tap "Pair device with pairing code".
     Keep that dialog visible (put Termux in split-screen or a floating
     window), because leaving it changes the port. It shows an address like
     192.168.1.5:37845 and a 6-digit code. In Termux:
         adb kill-server
         adb start-server
         adb pair <IP>:<pairing port>
     Enter the 6-digit code. You should see "Successfully paired".
     (If "localhost" gives a "protocol fault" error, use the phone's real
     Wi-Fi IP shown in the dialog instead.)
  8. Connect. Close the pairing dialog. The main Wireless debugging screen
     shows a DIFFERENT port next to "IP address & Port". Use that one:
         adb connect <IP>:<main port>
         adb devices
     The phone should be listed as "device".
  9. Start the script. The wake lock keeps Termux running when the screen
     is off or Termux is in the background:
         termux-wake-lock
         python minecraft_antiafk_phone.py
 10. Switch to Minecraft, join your server, stay in LANDSCAPE.
 11. Stop: go back to Termux and press Ctrl+C. Release the wake lock with
     `termux-wake-unlock`.

Next time (pairing is remembered): turn on Wireless debugging, read the new
port, run `adb connect <IP>:<port>`, then steps 9 and 10.

Troubleshooting:
  - "Aborted" during install: run the install as one command with -y.
  - "Connection refused" on connect: the port changed or you used the
    pairing port. Toggle Wireless debugging off/on, read the new main port,
    and connect right away. The phone must stay on the same Wi-Fi.
  - Wireless debugging switches itself off when Wi-Fi changes or the phone
    restarts, so the port is usually different each time.
  - Script stops after a while: turn off battery optimization for Termux in
    the phone's app settings.

=====================================================================
CALIBRATION (if taps miss their buttons)
=====================================================================
Button positions below are fractions of the screen based on the default
Bedrock touch layout. Turn on Developer options > "Pointer location", touch
each button, and divide the x by the screen width and the y by the screen
height (landscape) to get new fractions. Edit the values under "Positions"
below (in Termux: `nano minecraft_antiafk_phone.py`, save with Ctrl+O,
Enter, then exit with Ctrl+X).

Other notes:
  - The screen is only kept awake while the phone is plugged in.
  - Minecraft must stay in the foreground.
  - Some servers prohibit AFK bypassing or detect repetitive input. Check
    the server rules before using this.
"""

import random
import subprocess
import sys
import time

# ---------------- Settings ----------------
MIN_INTERVAL = 4        # min seconds between actions
MAX_INTERVAL = 12       # max seconds between actions
KEEP_SCREEN_ON = True   # stops the phone sleeping while plugged in
DEVICE_SERIAL = None    # e.g. "emulator-5554" if several devices are connected
LONG_PAUSE_MAX = 30     # occasional longer idle gaps, up to this many seconds
COMBO_CHANCE = 0.25     # chance of doing 2-3 actions in quick succession

# Positions as (x_fraction, y_fraction) of the landscape screen.
JOYSTICK = (0.14, 0.72)       # center of the left movement stick
JUMP_BUTTON = (0.87, 0.58)
SNEAK_BUTTON = (0.78, 0.74)
ATTACK_TAP = (0.62, 0.45)     # tapping the world swings / hits
LOOK_AREA = (0.60, 0.35)      # starting point for camera swipes
HOTBAR_Y = 0.94
HOTBAR_X_RANGE = (0.33, 0.67) # left edge of slot 1 to right edge of slot 9
# ------------------------------------------


def adb(*args):
    cmd = ["adb"]
    if DEVICE_SERIAL:
        cmd += ["-s", DEVICE_SERIAL]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def get_landscape_size():
    out = adb("shell", "wm", "size").stdout
    # Example: "Physical size: 1080x2400"
    try:
        size = out.strip().split(":")[-1].strip().split("x")
        a, b = int(size[0]), int(size[1])
    except (ValueError, IndexError):
        sys.exit("Couldn't read screen size. Is your phone connected? Try `adb devices`.")
    return max(a, b), min(a, b)  # (width, height) in landscape


W, H = 0, 0


def px(frac):
    return int(frac[0] * W), int(frac[1] * H)


def jitter(value, amount=12):
    return value + random.randint(-amount, amount)


def tap(frac):
    x, y = px(frac)
    adb("shell", "input", "tap", str(jitter(x)), str(jitter(y)))


def swipe(x1, y1, x2, y2, ms):
    adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms))


# ----- Actions -----
def jump():
    tap(JUMP_BUTTON)
    if random.random() < 0.2:  # sometimes jump twice
        time.sleep(random.uniform(0.15, 0.4))
        tap(JUMP_BUTTON)


def walk_back_and_forth():
    """Push the joystick one way, then the opposite way, to stay in place."""
    cx, cy = px(JOYSTICK)
    reach = int(random.uniform(0.07, 0.12) * H)
    dx, dy = random.choice([(0, -reach), (0, reach), (-reach, 0), (reach, 0)])
    ms = random.randint(250, 700)
    swipe(cx, cy, cx + dx, cy + dy, ms)
    time.sleep(random.uniform(0.1, 0.3))
    swipe(cx, cy, cx - dx, cy - dy, int(ms * random.uniform(0.85, 1.15)))


def look_around():
    x, y = px(LOOK_AREA)
    dx = random.randint(-int(0.12 * W), int(0.12 * W))
    dy = random.randint(-int(0.05 * H), int(0.05 * H))
    swipe(x, y, x + dx, y + dy, random.randint(200, 500))


def sneak():
    x, y = px(SNEAK_BUTTON)
    swipe(x, y, x, y, random.randint(300, 800))  # long press


def swing_arm():
    tap(ATTACK_TAP)


def switch_hotbar():
    slot = random.randint(0, 8)
    x_left, x_right = HOTBAR_X_RANGE
    frac_x = x_left + (slot + 0.5) * (x_right - x_left) / 9
    tap((frac_x, HOTBAR_Y))


# ----- Randomization -----
# Higher weight = more likely. The same action is never picked twice in a row.
ACTION_WEIGHTS = {
    jump: 3,
    walk_back_and_forth: 3,
    look_around: 4,
    sneak: 2,
    swing_arm: 2,
    switch_hotbar: 1,
}
_last_action = None


def pick_action():
    global _last_action
    choices = [a for a in ACTION_WEIGHTS if a is not _last_action]
    weights = [ACTION_WEIGHTS[a] for a in choices]
    _last_action = random.choices(choices, weights)[0]
    return _last_action


def next_delay():
    """Mostly mid-range gaps, sometimes quick follow-ups, sometimes long pauses."""
    r = random.random()
    if r < 0.12:
        return random.uniform(0.5, 2.0)
    if r < 0.20:
        return random.uniform(MAX_INTERVAL, LONG_PAUSE_MAX)
    mode = MIN_INTERVAL + 0.4 * (MAX_INTERVAL - MIN_INTERVAL)
    return random.triangular(MIN_INTERVAL, MAX_INTERVAL, mode)


def run_burst():
    """Do one action, or sometimes 2-3 in quick succession."""
    count = random.choice([2, 3]) if random.random() < COMBO_CHANCE else 1
    for i in range(count):
        action = pick_action()
        print(f"-> {action.__name__}")
        action()
        if i < count - 1:
            time.sleep(random.uniform(0.3, 1.2))


def main():
    global W, H
    if adb("get-state").stdout.strip() != "device":
        sys.exit("No device found. Check USB/wireless debugging and run `adb devices`.")

    W, H = get_landscape_size()
    print(f"Screen (landscape): {W}x{H}")

    if KEEP_SCREEN_ON:
        adb("shell", "svc", "power", "stayon", "true")

    print("Running. Make sure Minecraft is open in the foreground. Ctrl+C to stop.")
    try:
        while True:
            run_burst()
            time.sleep(next_delay())
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if KEEP_SCREEN_ON:
            adb("shell", "svc", "power", "stayon", "false")


if __name__ == "__main__":
    main()

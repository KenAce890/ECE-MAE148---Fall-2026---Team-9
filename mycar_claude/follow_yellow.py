#!/usr/bin/env python3
"""
Follow the dashed yellow center line continuously, through ClaudePilot.

Reads each new camera frame that ClaudePilot saves, finds the yellow dashes,
fits a line through them and steers to keep that line where it was at the start on row
LOOKAHEAD_Y, while renewing a short throttle command every frame.

Stops (and exits) when:
  - the driver takes back control (mode goes to user: Stop Vehicle / spacebar),
  - the yellow line is lost for LOST_S seconds,
  - MAX_S seconds have passed.
Each command expires after CMD_S seconds, so if this script dies the car stops.

Usage: python follow_yellow.py [THROTTLE] [MAX_S]
"""
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image

import claude_drive as cd

THROTTLE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.27
MAX_S = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

YELLOW_LO, YELLOW_HI = (15, 60, 90), (35, 255, 255)   # daylight dashes
ROI_TOP = 140          # position from the nearest dashes: on bends the far ones run sideways
HEADING_TOP = 110      # direction from all dashes below this row, so bends show up early
MIN_BLOB_PX = 6
LOOKAHEAD_Y = 170      # row where the line position is measured
TARGET_X = None        # where to hold the line on that row; None = wherever it is at the start
MAX_X_JUMP = 120       # an estimate this far off target is a misread, not a position
GAIN = 0.004           # steering per pixel of position error
HEADING_GAIN = 0.4     # steering per unit change in the line's direction (dx/dy) since the start
MAX_STEER = 0.45
MAX_STEER_STEP = 0.08  # largest steering change between frames
CMD_S = 0.3            # each command's lifetime (three frames at 10 Hz)
LOST_S = 0.8
LOG_DIR = os.path.join(cd.DIR, 'follow')


def fit(blobs):
    """Fit x = a*y + b through dash centroids; None if they don't span enough rows."""
    if len(blobs) < 2:
        return None
    xs, ys, ws = (np.array(v, float) for v in zip(*blobs))
    if ys.max() - ys.min() < 15:       # all blobs on one row: can't fit a direction
        return None
    return np.polyfit(ys, xs, 1, w=np.sqrt(ws))


def find_line(rgb, target_x=None):
    """Return (x at LOOKAHEAD_Y, direction dx/dy, blobs); x is None if the line isn't found."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv[HEADING_TOP:], YELLOW_LO, YELLOW_HI)
    _, _, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    blobs = [(c[0], c[1] + HEADING_TOP, s[4]) for s, c in zip(stats[1:], cents[1:]) if s[4] >= MIN_BLOB_PX]
    near = fit([b for b in blobs if b[1] >= ROI_TOP])
    if near is None:
        return None, None, blobs
    x = near[0] * LOOKAHEAD_Y + near[1]
    if target_x is not None and abs(x - target_x) > MAX_X_JUMP:
        return None, None, blobs
    whole = fit(blobs)
    return x, (whole if whole is not None else near)[0], blobs


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    if cd.status()['mode'] == 'user':
        sys.exit("Not handed over: set Mode to Full Auto first.")
    start = last_seen = time.time()
    last_frame = 0.0
    steering = 0.0
    target_x = TARGET_X
    n = 0
    reason = 'time limit'
    while time.time() - start < MAX_S:
        s = cd.status()
        if s['mode'] == 'user':
            reason = 'driver took control'
            break
        if s['frame_time'] <= last_frame:
            time.sleep(0.02)
            continue
        last_frame = s['frame_time']
        try:
            rgb = np.asarray(Image.open(cd.FRAME).convert('RGB'))
        except OSError:
            continue
        x, direction, blobs = find_line(rgb, target_x)
        now = time.time()
        if x is not None and target_x is None:
            target_x, start_direction = x, direction
            print(f"holding the line at x={target_x:.1f}, direction {start_direction:+.2f}")
        if x is None:
            if now - last_seen > LOST_S:
                reason = 'yellow line lost'
                break
            print(f"{now - start:5.1f}s  line not found ({len(blobs)} blobs), coasting")
            continue
        last_seen = now
        # the line bending right ahead makes dx/dy more negative, so steer right
        target = GAIN * (x - target_x) + HEADING_GAIN * (start_direction - direction)
        target = float(np.clip(target, -MAX_STEER, MAX_STEER))
        steering += float(np.clip(target - steering, -MAX_STEER_STEP, MAX_STEER_STEP))
        cd.write_cmd(steering, THROTTLE, CMD_S)
        n += 1
        print(f"{now - start:5.1f}s  line x={x:6.1f}  dir {direction:+.2f}  steer {steering:+.2f}  dashes {len(blobs)}")
        if n % 5 == 0:
            Image.fromarray(rgb).save(os.path.join(LOG_DIR, f'{n:04d}.jpg'))
    cd.write_cmd(0.0, 0.0, 0.0)
    print(f"stopped: {reason} after {time.time() - start:.1f}s, {n} commands")


if __name__ == '__main__':
    main()

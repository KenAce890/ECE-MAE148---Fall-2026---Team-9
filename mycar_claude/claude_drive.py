#!/usr/bin/env python3
"""
Claude's driving tool for the ClaudePilot part (run while manage.py drive is running).

Usage:
    python claude_drive.py status
    python claude_drive.py look [OUT]
    python claude_drive.py step STEERING THROTTLE SECONDS [OUT]
    python claude_drive.py go SECONDS [SPEED]
    python claude_drive.py stop

look   saves the latest camera frame to OUT (default /dev/shm/claude_pilot/look.jpg)
step   (drive mode) steers to STEERING (-1 left .. 1 right) and applies THROTTLE
       for SECONDS, waits until the car has stopped, then saves a fresh frame to OUT.
go     (supervise mode, manage.py started with --model) lets the CNN drive for
       SECONDS at SPEED x its own throttle (0..1, default 1). Renew before it runs out.
step and go are refused unless the driver has handed over with the controller.
stop   cancels any running step or go immediately.
"""
import json
import os
import shutil
import sys
import time

DIR = '/dev/shm/claude_pilot'
CMD = os.path.join(DIR, 'cmd.json')
LEASE = os.path.join(DIR, 'lease.json')
STATUS = os.path.join(DIR, 'status.json')
FRAME = os.path.join(DIR, 'frame.jpg')
DEFAULT_OUT = os.path.join(DIR, 'look.jpg')


def status():
    try:
        with open(STATUS) as f:
            return json.load(f)
    except (OSError, ValueError):
        sys.exit("No status: is `python manage.py drive` running in ~/mycar_claude?")


def wait_for_frame_after(t, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = status()
        if s['frame_time'] > t:
            return s
        time.sleep(0.05)
    sys.exit("No fresh camera frame: the drive loop may have stopped.")


def save_frame(out, s):
    shutil.copyfile(FRAME, out)
    steering = s.get('steering')
    line = (f"frame {out}  age {time.time() - s['frame_time']:.2f}s  mode {s['mode']}  "
            f"steering {steering if steering is None else f'{steering:+.2f}'}  throttle {s['throttle']:.2f}")
    if s.get('role') == 'supervise':
        line += f"  speed {s['speed']:.2f}"
    print(line)


def write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)
    return data


def write_cmd(steering, throttle, seconds):
    now = time.time()
    return write_json(CMD, {'id': int(now * 1000), 'created': now, 'until': now + seconds,
                            'steering': steering, 'throttle': throttle})


def write_lease(seconds, speed):
    now = time.time()
    return write_json(LEASE, {'id': int(now * 1000), 'created': now, 'until': now + seconds,
                              'speed': speed})


def main(argv):
    if not argv:
        sys.exit(__doc__)
    action = argv[0]

    if action == 'status':
        s = status()
        s['frame_age_s'] = round(time.time() - s['frame_time'], 2)
        print(json.dumps(s, indent=1))

    elif action == 'look':
        out = argv[1] if len(argv) > 1 else DEFAULT_OUT
        save_frame(out, wait_for_frame_after(time.time() - 0.5))

    elif action == 'step':
        steering, throttle, seconds = float(argv[1]), float(argv[2]), float(argv[3])
        out = argv[4] if len(argv) > 4 else DEFAULT_OUT
        s = status()
        if s['mode'] == 'user':
            sys.exit("Not handed over: the driver must press Start on the controller first.")
        cmd = write_cmd(steering, throttle, seconds)
        # confirm the part picked it up
        deadline = time.time() + 1.0
        while status().get('cmd_id') != cmd['id']:
            if time.time() > deadline:
                sys.exit("Command not picked up (mode changed or drive loop stalled).")
            time.sleep(0.02)
        time.sleep(max(0.0, cmd['until'] - time.time()) + 0.4)  # run, then let the car coast to a stop
        save_frame(out, wait_for_frame_after(time.time()))

    elif action == 'go':
        seconds = float(argv[1])
        speed = float(argv[2]) if len(argv) > 2 else 1.0
        s = status()
        if s.get('role') != 'supervise':
            sys.exit("Not in supervise mode: start manage.py with --model.")
        if s['mode'] == 'user':
            sys.exit("Not handed over: the driver must press Start on the controller first.")
        lease = write_lease(seconds, speed)
        deadline = time.time() + 1.0
        while status().get('cmd_id') != lease['id']:
            if time.time() > deadline:
                sys.exit("Go not picked up (mode changed or drive loop stalled).")
            time.sleep(0.02)
        print(f"go: CNN driving for {seconds:.1f}s at speed {speed:.2f}")

    elif action == 'stop':
        write_cmd(0.0, 0.0, 0.0)
        write_lease(0.0, 0.0)
        print("stopped")

    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])

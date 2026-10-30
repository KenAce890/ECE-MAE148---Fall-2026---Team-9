"""
ClaudePilot: lets Claude drive in short, self-expiring steps from camera frames.
ClaudeSupervisor (below): the CNN drives and Claude supervises it.

The vehicle loop calls run() every frame. It
  - saves the latest camera frame (and a status file) to CLAUDE_DIR so the
    claude_drive.py tool can look at it, and
  - outputs pilot/angle and pilot/throttle from the latest command file.

Safety:
  - Commands only take effect after the driver hands over with the controller
    (mode local_angle or local). In user mode the controller drives as normal.
  - Commands written before the hand-over are ignored, so a stale command can
    never fire the moment autopilot is engaged.
  - Each command has an expiry (at most CLAUDE_MAX_STEP_S seconds); after it the
    throttle drops to 0. If Claude stops sending commands, the car stops.
  - Throttle is clamped to 0..CLAUDE_MAX_THROTTLE (forward only).
"""
import json
import os
import time

import numpy as np
from PIL import Image


class ClaudePilot:
    def __init__(self, cfg):
        self.dir = cfg.CLAUDE_DIR
        self.max_throttle = cfg.CLAUDE_MAX_THROTTLE
        self.max_step_s = cfg.CLAUDE_MAX_STEP_S
        self.frame_period = 1.0 / cfg.CLAUDE_FRAME_HZ
        self.swap_rb = cfg.CLAUDE_SWAP_RB
        os.makedirs(self.dir, exist_ok=True)
        self.cmd_path = os.path.join(self.dir, 'cmd.json')
        # drop any command left over from a previous run
        if os.path.exists(self.cmd_path):
            os.remove(self.cmd_path)

        self.mode = 'user'
        self.engaged_at = None
        self.cmd = None
        self.cmd_mtime = None
        self.steering = 0.0
        self.last_frame_time = 0.0

    def _write_atomic(self, name, write):
        tmp = os.path.join(self.dir, '.' + name)
        write(tmp)
        os.replace(tmp, os.path.join(self.dir, name))

    def _read_cmd(self):
        try:
            mtime = os.stat(self.cmd_path).st_mtime
        except FileNotFoundError:
            return
        if mtime == self.cmd_mtime:
            return
        self.cmd_mtime = mtime
        try:
            with open(self.cmd_path) as f:
                self.cmd = json.load(f)
        except (OSError, ValueError):
            self.cmd = None

    def run(self, img, mode):
        now = time.time()
        self._track_mode(mode, now)
        self._read_cmd()
        throttle = 0.0
        active = False
        cmd = self.cmd
        if (cmd is not None and self.engaged_at is not None
                and cmd.get('created', 0) >= self.engaged_at):
            self.steering = float(np.clip(cmd.get('steering', 0.0), -1.0, 1.0))
            until = min(cmd.get('until', 0), cmd.get('created', 0) + self.max_step_s)
            if now < until:
                throttle = float(np.clip(cmd.get('throttle', 0.0), 0.0, self.max_throttle))
                active = True
        if self.engaged_at is None:
            self.steering = 0.0

        self._save_frame(img, now, {
            'role': 'drive',
            'cmd_id': cmd.get('id') if cmd else None,
            'active': active,
            'steering': self.steering,
            'throttle': throttle,
        })
        return self.steering, throttle

    def _track_mode(self, mode, now):
        """Note when the driver hands over (mode leaves 'user') or takes back control."""
        mode = mode or 'user'
        if mode != self.mode:
            self.engaged_at = now if mode != 'user' else None
            self.mode = mode

    def _save_frame(self, img, now, status):
        if img is None or now - self.last_frame_time < self.frame_period:
            return
        self.last_frame_time = now
        frame = img[:, :, ::-1] if self.swap_rb else img
        self._write_atomic('frame.jpg', lambda p: Image.fromarray(np.uint8(frame)).save(p, 'JPEG', quality=90))
        status = dict(status, frame_time=now, mode=self.mode, engaged_at=self.engaged_at)
        self._write_atomic('status.json', lambda p: open(p, 'w').write(json.dumps(status)))


class ClaudeSupervisor(ClaudePilot):
    """
    The CNN drives; Claude supervises.

    Passes the model's pilot/angle and pilot/throttle through, but only while
    Claude holds an unexpired "go" lease (lease.json, written by
    `claude_drive.py go`). The lease also sets a speed factor (0..1) applied to
    the model's throttle. When the lease runs out (Claude stopped checking in,
    or sent `stop`), throttle drops to 0. The same hand-over rules as
    ClaudePilot apply: leases written before the driver pressed Start are
    ignored, and a lease lasts at most CLAUDE_MAX_LEASE_S seconds.

    Use Full Auto: in Auto Steer the driver's stick sets the throttle, so a
    stop from Claude has no effect.
    """
    def __init__(self, cfg):
        super().__init__(cfg)
        self.max_lease_s = cfg.CLAUDE_MAX_LEASE_S
        self.cmd_path = os.path.join(self.dir, 'lease.json')
        if os.path.exists(self.cmd_path):
            os.remove(self.cmd_path)

    def run(self, img, mode, pilot_angle, pilot_throttle):
        now = time.time()
        self._track_mode(mode, now)
        self._read_cmd()

        lease = self.cmd
        speed = 0.0
        if (lease is not None and self.engaged_at is not None
                and lease.get('created', 0) >= self.engaged_at):
            until = min(lease.get('until', 0), lease.get('created', 0) + self.max_lease_s)
            if now < until:
                speed = float(np.clip(lease.get('speed', 1.0), 0.0, 1.0))

        throttle = 0.0
        if pilot_throttle is not None:
            throttle = float(np.clip(pilot_throttle * speed, 0.0, self.max_throttle))

        self._save_frame(img, now, {
            'role': 'supervise',
            'cmd_id': lease.get('id') if lease else None,
            'active': speed > 0,
            'speed': speed,
            'model_steering': pilot_angle,
            'model_throttle': pilot_throttle,
            'steering': pilot_angle,
            'throttle': throttle,
        })
        return pilot_angle, throttle

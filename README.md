# ECE-MAE148 - Fall26 Team-9
Documenting Code and Design of Team 9 for Building Autonomous Vehicle for ECE/MAE148 F26 @ UCSD

## Car software

Donkeycar 5.4 car folders for a Raspberry Pi 5 car with a VESC motor controller,
OAK-D Lite camera and Logitech F710 gamepad.

| Folder | What it is | Run |
|---|---|---|
| `mycar/` | Main car: manual driving, data recording, driving trained models | `python manage.py drive [--model models/mypilot.tflite --type tflite_linear]` |
| `mycar_cv/` | Follows the yellow center line with OpenCV (no training) | `python manage.py drive`, then Start |
| `mycar_claude/` | Claude drives in short, self-expiring steps; or, with `--model`, the CNN drives and Claude supervises (go/stop/speed) | `python manage.py drive [--model ../mycar/models/mypilot.tflite --type tflite_linear]`, then Start; Claude uses `claude_drive.py` |

Notes:
- `my_joystick.py` maps the F710 in DirectInput (D) mode (`CONTROLLER_TYPE = 'custom'`).
- `mycar/vesc_calibrate.py` sets servo position and duty cycle interactively (wheels off the ground).
- The VESC must be configured FOC **sensorless**; the motor has no hall sensor cable.
- The OAK-D Lite needs `depthai` 2.33 (2.21 returns blank frames) and the Pi 5's
  `usb_max_current_enable=1`.
- `data/`, `models/` and `logs/` are not tracked.
- `donkeycar-patches/` has fixes the car needs on top of donkeycar 5.4.0; see its README.

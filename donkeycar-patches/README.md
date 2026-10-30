# donkeycar 5.4.0 fixes for this car

`donkeycar-5.4.0-car-fixes.patch` fixes three bugs in donkeycar 5.4.0 that this
car hits. Without it, plain 5.4.0 crashes as described below.

| File | Fix | Symptom without it |
|---|---|---|
| `donkeycar/parts/actuator.py` | VESC: read the firmware-version reply until the whole packet has arrived (pyvesc decodes as soon as 4 bytes arrive), retry the connection, start the heartbeat only once connected | `manage.py drive` fails at startup with `ValueError: invalid literal for int() with base 10: 'None'`, and Ctrl-C hangs |
| `donkeycar/parts/tub_v2.py` | Depth images: `ext=` -> `extension=` when saving | Recording crashes on the first frame with an OAK-D (`TypeError: Tub._image_file_name() got an unexpected keyword argument 'ext'`) |
| `donkeycar/templates/complete.py` | Pass `IMAGE_W`/`IMAGE_H` to the OAK-D camera | OAK-D records 640x480 regardless of the configured image size |

## Apply it

On the Pi, in a git clone of donkeycar installed in editable mode:

```bash
git clone https://github.com/autorope/donkeycar ~/projects/donkeycar
cd ~/projects/donkeycar
git checkout 5.4.0
git apply /path/to/robocar/donkeycar-patches/donkeycar-5.4.0-car-fixes.patch
pip install -e ".[pi]"
```

The `complete.py` fix only affects car folders created afterwards with
`donkey createcar`; the car folders in this repo already include it.

## Other setup the car needs

- `pip install "depthai==2.33.0.0"`: with 2.21 the OAK-D Lite returns blank frames.
- `usb_max_current_enable=1` in `/boot/firmware/config.txt` (Pi 5): without it the
  OAK-D trips the USB current limit and every USB device resets.
- pyvesc from git, for servo support:
  `pip install git+https://github.com/LiamBindle/PyVESC.git@master`

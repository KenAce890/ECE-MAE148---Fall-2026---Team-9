"""
Logitech F710 in DirectInput (D) mode, which Linux reports as a
"Logitech Cordless RumblePad 2". Same controls as donkeycar's F710 mapping
(CONTROLLER_TYPE = 'F710'), with the D-mode axis and button codes.

Used when myconfig.py has CONTROLLER_TYPE = 'custom'.
Run `python my_joystick.py` to print each control's name as you press it.
"""
from donkeycar.parts.controller import LogitechJoystick, LogitechJoystickController


class MyJoystick(LogitechJoystick):
    def __init__(self, *args, **kwargs):
        super(MyJoystick, self).__init__(*args, **kwargs)

        self.axis_names = {
            0x00: 'left_stick_horz',
            0x01: 'left_stick_vert',
            0x02: 'right_stick_horz',
            0x05: 'right_stick_vert',

            0x10: 'dpad_leftright', # 1 is right, -1 is left
            0x11: 'dpad_up_down', # 1 is down, -1 is up
        }

        # D mode numbers the buttons 1-12 in this order
        self.button_names = {
            0x130: 'X',
            0x131: 'A',
            0x132: 'B',
            0x133: 'Y',

            0x134: 'L1',
            0x135: 'R1',
            0x136: 'L2',
            0x137: 'R2',

            0x138: 'back',
            0x139: 'start',

            0x13a: 'left_stick_press',
            0x13b: 'right_stick_press',
        }


class MyJoystickController(LogitechJoystickController):
    def init_js(self):
        try:
            self.js = MyJoystick(self.dev_fn)
            self.js.init()
        except FileNotFoundError:
            self.js = None
        return self.js is not None


if __name__ == "__main__":
    js = MyJoystick('/dev/input/js0')
    js.init()
    print("Press buttons and move sticks (Ctrl-C to quit)...")
    while True:
        button, button_state, axis, axis_val = js.poll()
        if button is not None and button_state == 1:
            print("button:", button)
        if axis is not None and abs(axis_val) > 0.5:
            print("axis:", axis, round(axis_val, 2))

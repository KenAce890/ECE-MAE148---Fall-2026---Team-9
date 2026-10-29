"""
Interactive VESC steering/throttle calibration.
KEEP THE WHEELS OFF THE GROUND.

Commands:
  s <0.0-1.0>    set servo position, e.g. "s 0.5"
  t <-1.0-1.0>   set duty cycle for 1 second then stop, e.g. "t 0.05"
  q              quit
"""
import time
from donkeycar.parts.actuator import VESC

PORT = "/dev/serial/by-id/usb-STMicroelectronics_ChibiOS_RT_Virtual_COM_Port_304-if00"

# donkeycar's VESC part handles the flaky pyvesc connect; use its pyvesc handle
v = VESC(PORT).v
print(__doc__)
try:
    while True:
        cmd = input("> ").strip().split()
        if not cmd:
            continue
        if cmd[0] == "q":
            break
        try:
            val = float(cmd[1])
        except (IndexError, ValueError):
            print("need a number")
            continue
        if cmd[0] == "s":
            v.set_servo(max(0.0, min(1.0, val)))
        elif cmd[0] == "t":
            v.set_duty_cycle(max(-1.0, min(1.0, val)))
            time.sleep(1)
            v.set_duty_cycle(0)
finally:
    v.set_duty_cycle(0)
    v.stop_heartbeat()
    v.serial_port.close()

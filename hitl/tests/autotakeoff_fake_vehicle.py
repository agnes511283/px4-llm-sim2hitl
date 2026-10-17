#!/usr/bin/env python3
"""Run FW_SkySurfer_HIL_AutoTakeoff.py against a fake PX4 and a point-mass aircraft.

No bridge, serial port, model or flight controller is used: this process plays
the bridge agent port. It checks the script's sequence and hand-overs, not the
aircraft dynamics. Real time, about 90 s.
  /usr/bin/python3 -B hil_bridge/tests/autotakeoff_fake_vehicle.py
"""
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

os.environ.setdefault('MAVLINK20', '1')
from pymavlink.dialects.v20 import common as mav

SCRIPT = Path(__file__).resolve().parents[1]/'autotakeoff/FW_SkySurfer_HIL_AutoTakeoff.py'
MASS, WEIGHT, THRUST, WING, RHO = 1.5, 14.7, 14., .3056, 1.225


class FakeVehicle(threading.Thread):
    def __init__(self, hitl=1):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.settimeout(.002)
        self.port = self.sock.getsockname()[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('127.0.0.1', 0))
            self.script_port = s.getsockname()[1]
        self.out = mav.MAVLink(None, srcSystem=1, srcComponent=1)
        self.qgc = mav.MAVLink(None, srcSystem=255, srcComponent=190)
        self.parser = mav.MAVLink(None)
        self.parser.robust_parsing = True
        self.hitl = hitl
        self.mode, self.armed = 4, False
        self.v = self.h = self.gamma = 0.
        self.theta = math.radians(.86)
        self.sticks = (0, 0, 0, 0)
        self.manual = []                 # (time, sticks) of every MANUAL_CONTROL from the script
        self.commands = []
        self.pilot = None                # QGC sticks to pass on, as the bridge does
        self.running = True

    def send(self, message, encoder=None):
        self.sock.sendto(message.pack(encoder or self.out), ('127.0.0.1', self.script_port))

    def handle(self, m, now):
        kind = m.get_type()
        if kind == 'MANUAL_CONTROL':
            self.sticks = (m.x, m.y, m.z, m.r)
            self.manual.append((now, self.sticks))
        elif kind == 'COMMAND_LONG':
            self.commands.append((m.command, m.param1, m.param2))
            if m.command == mav.MAV_CMD_DO_SET_MODE:
                self.mode = int(m.param2)
            elif m.command == mav.MAV_CMD_COMPONENT_ARM_DISARM:
                self.armed = bool(m.param1) and self.mode == 7 and self.sticks[2] < 50
        elif kind == 'PARAM_REQUEST_READ':
            name = m.param_id if isinstance(m.param_id, str) else m.param_id.decode()
            name = name.rstrip('\0')
            if name == 'SYS_HITL':       # PX4 sends int32 bytes in the float field
                import struct
                value = struct.unpack('<f', struct.pack('<i', self.hitl))[0]
                self.send(mav.MAVLink_param_value_message(b'SYS_HITL', value, mav.MAV_PARAM_TYPE_INT32, 1, 0))
            elif name == 'FW_MAN_P_MAX':
                self.send(mav.MAVLink_param_value_message(b'FW_MAN_P_MAX', 30., mav.MAV_PARAM_TYPE_REAL32, 1, 0))

    def physics(self, dt):
        fresh = self.manual and time.monotonic()-self.manual[-1][0] < .5
        x, _, z, _ = self.sticks if fresh else (0, 0, 0, 0)
        throttle = z/1000 if self.armed else 0.
        if self.v > 5:
            self.theta += (math.radians(-30*x/1000)-self.theta)*min(1, dt/.3)
        lift = .5*RHO*self.v**2*WING*5*(self.theta-self.gamma+math.radians(4.27))
        airborne = self.h > 0 or lift > WEIGHT
        drag = .01725*self.v**2+(0 if airborne else .2*max(0, WEIGHT-lift))
        self.v = max(0, self.v+(throttle*THRUST-drag-WEIGHT*math.sin(self.gamma))/MASS*dt)
        if airborne and self.v > 3:
            self.gamma += (lift-WEIGHT*math.cos(self.gamma))/(MASS*self.v)*dt
            self.h = max(0, self.h+self.v*math.sin(self.gamma)*dt)
        else:
            self.gamma = 0.

    def run(self):
        last = time.monotonic()
        tick = 0
        while self.running:
            try:
                for m in self.parser.parse_buffer(self.sock.recv(65536)) or []:
                    self.handle(m, time.monotonic())
            except (socket.timeout, ConnectionError):
                pass
            now = time.monotonic()
            if now-last < .02:
                continue
            self.physics(now-last)
            last = now
            tick += 1
            boot = int(now*1000) & 0xffffffff
            self.send(mav.MAVLink_attitude_message(boot, 0, self.theta, 0, 0, 0, 0))
            if tick % 3 == 0:
                climb = self.v*math.sin(self.gamma)
                self.send(mav.MAVLink_local_position_ned_message(boot, 0, 0, -self.h, self.v, 0, -climb))
                self.send(mav.MAVLink_vfr_hud_message(self.v, self.v, 0, int(self.sticks[2]/10), self.h, climb))
            if tick % 10 == 0:           # heartbeat faster than PX4's 1 Hz keeps the test short
                base = 81 | (128 if self.armed else 0)
                self.send(mav.MAVLink_heartbeat_message(mav.MAV_TYPE_FIXED_WING, mav.MAV_AUTOPILOT_PX4,
                                                        base, self.mode << 16, 4, 3))
            if self.pilot is not None and tick % 2 == 0:
                self.send(mav.MAVLink_manual_control_message(1, *self.pilot, 0), self.qgc)


def launch(vehicle, folder, *extra):
    return subprocess.Popen([sys.executable, '-B', '-u', str(SCRIPT), 'takeoff', '--bridge-port', str(vehicle.port),
                             '--listen-port', str(vehicle.script_port), '--log-dir', str(folder), '--takeoff-throttle', '.60', '--cruise-throttle', '.50', '--rotate-cas', '15', '--climb-pitch', '15', *extra],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def wait(condition, timeout, what):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        if condition():
            return
        time.sleep(.05)
    raise AssertionError('timeout: '+what)


def status(folder):
    try:
        return json.loads((folder/'status.json').read_text())
    except (OSError, ValueError):
        return {}


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)

        # 1. Not a HIL flight controller: no stick stream, no command at all.
        vehicle = FakeVehicle(hitl=0)
        vehicle.start()
        process = launch(vehicle, folder)
        output = process.communicate(timeout=20)[0]
        assert process.returncode == 2 and 'SYS_HITL=0' in output, output
        assert not vehicle.manual and not vehicle.commands, (vehicle.manual[:1], vehicle.commands)
        vehicle.running = False
        print('PASS refuses when SYS_HITL is not 1')

        # 2. Ground to level flight.
        vehicle = FakeVehicle()
        vehicle.start()
        process = launch(vehicle, folder)
        wait(lambda: status(folder).get('state') == 'cruise', 70, 'cruise')
        assert vehicle.commands[0][0] == mav.MAV_CMD_DO_SET_MODE and vehicle.commands[0][2] == 7
        assert {c[0] for c in vehicle.commands} == {mav.MAV_CMD_DO_SET_MODE, mav.MAV_CMD_COMPONENT_ARM_DISARM}
        gaps = [b[0]-a[0] for a, b in zip(vehicle.manual, vehicle.manual[1:])]
        assert max(gaps) < .2, max(gaps)
        wait(lambda: status(folder).get('offboard_entry_stable_s', 0) >= 5, 40, 'Offboard entry conditions for 5 s')
        s = status(folder)
        assert abs(s['height_m']-100) < 15 and 15 <= s['cas_mps'] <= 25, s
        print('PASS takeoff to level flight:', {k: s[k] for k in ('height_m', 'cas_mps', 'climb_mps', 'pitch_deg', 'throttle_percent')})

        # 3. Sticks are frozen while PX4 is in Offboard, and move again afterwards.
        vehicle.mode = 6
        time.sleep(1.)
        start = time.monotonic()
        time.sleep(2.)
        frozen = {sticks for stamp, sticks in vehicle.manual if stamp >= start}
        assert len(frozen) == 1, frozen
        vehicle.mode = 7
        print('PASS sticks frozen in Offboard:', frozen)

        # 4. QGC sticks held still do nothing; moving them hands control back.
        vehicle.pilot = (0, 0, 100, 0)
        time.sleep(1.5)
        assert process.poll() is None and status(folder)['qgc_joystick_seen']
        vehicle.pilot = (0, 0, 400, 0)
        output = process.communicate(timeout=5)[0]
        assert process.returncode == 0 and 'pilot has control' in output, output
        time.sleep(.3)
        assert time.monotonic()-vehicle.manual[-1][0] > .25
        print('PASS QGC stick movement releases the script')

        # 5. Already flying: a new takeoff is refused without touching the sticks.
        vehicle.pilot = None
        count = len(vehicle.manual)
        process = launch(vehicle, folder)
        output = process.communicate(timeout=20)[0]
        assert process.returncode == 2 and 'takeoff starts only from the ground' in output, output
        assert len(vehicle.manual) == count
        vehicle.running = False
        print('PASS refuses to start in the air')


if __name__ == '__main__':
    main()

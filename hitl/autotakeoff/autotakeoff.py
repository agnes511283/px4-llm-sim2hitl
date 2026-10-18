#!/usr/bin/env python3
"""HIL scripted pilot for takeoff and level flight.

Connects to the HIL bridge agent port and flies like the QGC joystick does:
MANUAL_CONTROL in Stabilized. Sequence: Stabilized, arm, takeoff throttle,
pitch up at the rotate airspeed, climb to the target height, then wings level
with a slow altitude hold. The sticks are frozen while PX4 is in Offboard.

  takeoff   run the sequence (refuses unless PX4 reads back SYS_HITL=1)
  status    print the current flight state (works with or without a takeoff running)
  stop      ask a running takeoff to release the sticks
  reboot    restart PX4 (SYS_HITL=1 only, after the model has stopped; force-disarms
            first if needed). Do this after every stopped model, crash or flight
            termination, before the next run

The bridge gives this script's MANUAL_CONTROL priority over QGC's and passes
QGC's joystick frames here instead; moving the QGC sticks, Ctrl+C or `stop`
ends the stream and QGC's joystick is back about 0.2 s later.
No parameter is written. By default, takeoff sends set-mode Stabilized and
arm (plus disarm when a takeoff is abandoned on the ground). With --after,
a selected commands/SCRIPT.py sequence runs after a stable successful takeoff.
The shipped after_takeoff_template is empty.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import time

os.environ.setdefault('MAVLINK20', '1')
try:
    from pymavlink.dialects.v20 import common as mav
except ImportError as exc:
    raise SystemExit('Missing pymavlink; run the platform HIL launcher with --check-python') from exc

HERE = Path(__file__).resolve().parent
BRIDGE_ROOT = HERE.parent
LOG_DIR = BRIDGE_ROOT/'logs/autotakeoff'
# The moved standalone script and direct test imports share this package root.
if str(BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_ROOT))
from commands.sequence import load_script
STABILIZED, OFFBOARD = 7, 6           # PX4 custom main modes
SOURCE = (254, 190)                   # this script as a second ground station
TARGET = (1, 1)
TAKEOVER_STICK = 150                  # QGC stick movement (of 1000) that hands control back
CAPTURE_FRAME = struct.Struct('<dBI')  # same raw capture layout as 06_pi_software


def clamp(value, low, high):
    return max(low, min(high, value))


def text(value):
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode('ascii', 'replace')
    return value.rstrip('\0')


class Link:
    """UDP to the bridge agent port; decodes what the flight controller sends."""

    def __init__(self, listen_port, bridge_port, record=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', listen_port))
        self.sock.setblocking(False)
        self.bridge = ('127.0.0.1', bridge_port)
        self.mav = mav.MAVLink(None, srcSystem=SOURCE[0], srcComponent=SOURCE[1])
        self.parser = mav.MAVLink(None)
        self.parser.robust_parsing = True
        self.record = record

    def send(self, message):
        raw = message.pack(self.mav)
        self.sock.sendto(raw, self.bridge)
        self._capture(5, raw)

    def receive(self):
        messages = []
        for _ in range(256):
            try:
                raw = self.sock.recv(65536)
            except (BlockingIOError, ConnectionError):
                break
            self._capture(1, raw)
            try:
                messages += self.parser.parse_buffer(raw) or []
            except mav.MAVError:
                pass
        return messages

    def _capture(self, channel, raw):
        if self.record:
            self.record.write(CAPTURE_FRAME.pack(time.monotonic(), channel, len(raw))+raw)

    def close(self):
        self.sock.close()
        if self.record:
            self.record.close()


class Vehicle:
    """Latest telemetry, with arrival times so stale data is never used."""

    def __init__(self):
        self.mode = self.armed = self.vehicle_type = None
        self.sub_mode = None
        self.cas = self.height = self.climb = self.pitch = self.roll = math.nan
        self.seen = {}
        self.params = {}
        self.texts = []
        self.pilot = None             # QGC sticks passed on by the bridge: (x, y, z, r)
        self.target_pitch = self.target_thrust = math.nan

    def update(self, message, now):
        kind = message.get_type()
        system = message.get_srcSystem()
        if kind == 'MANUAL_CONTROL' and system != TARGET[0]:
            self.pilot = (message.x, message.y, message.z, message.r)
            self.seen['pilot'] = now
            return
        if (system, message.get_srcComponent()) != TARGET:
            return
        if kind == 'HEARTBEAT':
            self.mode = (message.custom_mode >> 16) & 255
            self.sub_mode = (message.custom_mode >> 24) & 255
            self.armed = bool(message.base_mode & mav.MAV_MODE_FLAG_SAFETY_ARMED)
            self.vehicle_type = message.type
        elif kind == 'VFR_HUD':
            self.cas = message.airspeed
        elif kind == 'LOCAL_POSITION_NED':
            self.height, self.climb = -message.z, -message.vz
        elif kind == 'ATTITUDE':
            self.pitch, self.roll = math.degrees(message.pitch), math.degrees(message.roll)
        elif kind == 'ATTITUDE_TARGET':
            q = message.q
            self.target_pitch = math.degrees(math.asin(clamp(2*(q[0]*q[2]-q[3]*q[1]), -1, 1)))
            self.target_thrust = message.thrust
        elif kind == 'PARAM_VALUE':
            value = message.param_value
            if message.param_type == mav.MAV_PARAM_TYPE_INT32:   # PX4 sends the int32 bytes in the float field
                value = struct.unpack('<i', struct.pack('<f', value))[0]
            self.params[text(message.param_id)] = value
            return
        elif kind == 'STATUSTEXT':
            self.texts = (self.texts+[text(message.text)])[-5:]
            return
        else:
            return
        self.seen[kind] = now

    def fresh(self, now):
        limits = dict(HEARTBEAT=3., VFR_HUD=1., LOCAL_POSITION_NED=1., ATTITUDE=1.)
        return (all(now-self.seen.get(kind, -math.inf) <= limit for kind, limit in limits.items())
                and all(math.isfinite(value) for value in
                        (self.cas, self.height, self.climb, self.pitch, self.roll)))

    def entry_ready(self, throttle):
        """The Pi's Offboard entry conditions, as seen from here (information only)."""
        return bool(self.mode == STABILIZED and self.armed and self.height >= 60
                    and 15 <= self.cas <= 25 and abs(self.roll) <= 5 and abs(self.climb) <= 1.5
                    and -15 <= self.pitch <= 20 and throttle >= .2)


def snapshot(vehicle, now, **extra):
    def number(value):
        return round(value, 2) if isinstance(value, float) and math.isfinite(value) else None
    return dict(time=time.strftime('%Y-%m-%d %H:%M:%S'), telemetry_fresh=vehicle.fresh(now),
                px4_mode=vehicle.mode, armed=vehicle.armed, cas_mps=number(vehicle.cas),
                height_m=number(vehicle.height), climb_mps=number(vehicle.climb),
                pitch_deg=number(vehicle.pitch), roll_deg=number(vehicle.roll),
                px4_messages=vehicle.texts, **extra)


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2)+'\n')
    temporary.replace(path)


class Takeoff:
    def __init__(self, args, link):
        self.a = args
        self.link = link
        self.vehicle = Vehicle()
        self.state = 'connect'
        self.since = time.monotonic()
        self.reason = ''
        self.sticks = [0, 0, 0, 0]    # x pitch, y roll, z throttle 0..1000, r yaw
        self.streaming = False
        self.pitch_command = 0.       # deg, positive nose up
        self.pitch_scale = 30.        # FW_MAN_P_MAX, read back before arming
        self.pilot_reference = None
        self.next = dict(heartbeat=0., command=0., param=0., status=0., log=0., echo=0.)
        self.ready_since = None
        self.airborne = False
        self.stop = False
        self.stop_reason = 'stop requested'
        self.actor_return_slew = False
        self.after_sequence = getattr(args, 'after_sequence', None)
        self.after_ready_since = self.after_wait_started = None
        self.climb_timed_out = False
        self.mode_command_id = mav.MAV_CMD_DO_SET_MODE

    # --- helpers ---------------------------------------------------------
    def go(self, state, reason=''):
        self.state, self.since, self.reason = state, time.monotonic(), reason
        print(f'[{time.strftime("%H:%M:%S")}] {state}' + (f': {reason}' if reason else ''), flush=True)

    def command(self, command, *params):
        params = list(params)+[0]*(7-len(params))
        self.link.send(mav.MAVLink_command_long_message(*TARGET, command, 0, *params))

    def request_param(self, name):
        self.link.send(mav.MAVLink_param_request_read_message(*TARGET, name.encode(), -1))

    def set_pitch(self, target, dt, rate=12., max_step=None):
        step = rate*dt
        if max_step is not None:
            step = min(step, max_step)
        self.pitch_command += clamp(target-self.pitch_command, -step, step)
        self.sticks[0] = int(round(-1000*clamp(self.pitch_command/self.pitch_scale, -1, 1)))

    def set_throttle(self, target, dt, rate=.5, max_step=None):
        current = self.sticks[2]/1000
        step = rate*dt
        if max_step is not None:
            step = min(step, max_step)
        self.sticks[2] = int(round(1000*(current+clamp(target-current, -step, step))))

    def release(self, reason):
        self.streaming = False
        if self.after_sequence:
            self.after_sequence.cancel(reason)
        self.go('released', reason)

    def after_step(self, now):
        """Run an explicitly selected sequence after a successful stable climb."""
        script = self.after_sequence
        if not self.vehicle.armed:
            return False
        if script is None or script.state not in ('waiting', 'running'):
            return False
        if script.state == 'waiting':
            if self.after_wait_started is None:
                self.after_wait_started = now
            if self.climb_timed_out:
                script.state, script.reason = 'failed', 'climb timed out; post-takeoff script not started'
                self.release(script.reason)
                return True
            v = self.vehicle
            ready = (self.streaming and v.fresh(now) and v.armed and v.mode == STABILIZED
                     and abs(v.height-self.a.altitude) <= 5 and self.a.rotate_cas <= v.cas <= 30
                     and abs(v.roll) <= 5 and abs(v.climb) <= 1.5 and -15 <= v.pitch <= 20)
            if not ready:
                self.after_ready_since = None
            elif self.after_ready_since is None:
                self.after_ready_since = now
            if ready and now-self.after_ready_since >= self.a.after_stable_seconds:
                script.begin()
                print('Post-takeoff command script started: ' + script.name, flush=True)
            elif now-self.after_wait_started >= self.a.after_timeout:
                script.state, script.reason = 'failed', 'post-takeoff readiness timed out'
                self.release(script.reason)
                return True
        if script.state == 'running':
            script.tick(self, now)
            return True
        return False

    # --- one control step --------------------------------------------------
    def step(self, now, dt):
        v, a = self.vehicle, self.a
        for message in self.link.receive():
            v.update(message, now)
        if now >= self.next['heartbeat']:
            self.next['heartbeat'] = now+1
            self.link.send(mav.MAVLink_heartbeat_message(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID, 0, 0, 0, 3))
        elapsed = now-self.since
        on_ground = not self.airborne

        if self.stop and self.state not in ('released', 'abandon'):
            if self.streaming and on_ground and self.state in ('arm', 'roll'):
                self.go('abandon', self.stop_reason)
            else:
                self.release(self.stop_reason)
        elif self.streaming and self.pilot_takeover(now):
            self.release('QGC sticks moved: pilot has control')
        elif self.streaming and not v.fresh(now):
            if on_ground and self.state in ('arm', 'roll'):
                self.go('abandon', 'telemetry lost')
            else:
                self.release('telemetry lost')

        elif self.state == 'connect':
            if v.fresh(now):
                self.go('check')
            elif elapsed > 15:
                self.release('no telemetry from the bridge agent port; is the bridge running?')
        elif self.state == 'check':
            if now >= self.next['param']:
                self.next['param'] = now+.5
                self.request_param('SYS_HITL' if 'SYS_HITL' not in v.params else 'FW_MAN_P_MAX')
            if 'SYS_HITL' in v.params and v.params['SYS_HITL'] != 1:
                self.release(f'SYS_HITL={v.params["SYS_HITL"]}: not a HIL flight controller, refusing')
            elif 'SYS_HITL' in v.params and 'FW_MAN_P_MAX' in v.params:
                self.pitch_scale = float(v.params['FW_MAN_P_MAX'])
                if not math.isfinite(self.pitch_scale) or self.pitch_scale <= 0:
                    self.release('FW_MAN_P_MAX must be finite and positive')
                elif v.vehicle_type != mav.MAV_TYPE_FIXED_WING:
                    self.release('flight controller is not a fixed wing')
                elif v.armed or v.cas > 5 or abs(v.height) > 5:
                    self.release('not disarmed on the ground: takeoff starts only from the ground')
                else:
                    self.streaming = True
                    self.go('mode')
            elif elapsed > 8:
                self.release('SYS_HITL / FW_MAN_P_MAX could not be read back')
        elif self.state == 'mode':
            if v.mode == STABILIZED and elapsed >= 1:      # sticks must be established before arming
                self.go('arm')
            elif now >= self.next['command']:
                self.next['command'] = now+1
                self.command(mav.MAV_CMD_DO_SET_MODE, 1, STABILIZED)
            if elapsed > 8:
                self.release('PX4 did not enter Stabilized')
        elif self.state == 'arm':
            if v.armed:
                self.go('roll')
            elif now >= self.next['command']:
                self.next['command'] = now+1.5
                self.command(mav.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            if elapsed > 10:
                self.go('abandon', 'PX4 did not arm: '+' | '.join(v.texts[-2:]))
        elif self.state == 'roll':
            self.set_throttle(a.takeoff_throttle, dt, rate=1.)
            if v.cas >= a.rotate_cas:
                self.go('climb')
            elif elapsed > 40:
                self.go('abandon', f'rotate airspeed not reached (CAS {v.cas:.1f} m/s)')
        elif self.state == 'climb':
            self.airborne = self.airborne or v.height > 3
            self.set_throttle(a.takeoff_throttle, dt)
            self.set_pitch(a.climb_pitch, dt, rate=30.)
            if v.height >= a.altitude-2:
                self.go('cruise')
            elif elapsed > 180:
                self.climb_timed_out = True
                self.go('cruise', f'climb timed out at {v.height:.0f} m')
        elif self.state == 'cruise':
            if self.after_step(now):
                pass  # The command sequence owns sticks for this tick.
            elif v.mode != OFFBOARD:                           # frozen sticks while the Pi is in control
                returning = a.actor_handover and self.actor_return_slew
                # Actor fallback resumes gently and cannot catch up a late tick
                # with a larger command step. The original pilot path is unchanged.
                self.set_throttle(a.cruise_throttle, dt, rate=.25 if returning else .5,
                                  max_step=.25/a.rate if returning else None)
                hold = clamp(a.altitude_gain*(a.altitude-v.height)-a.climb_damping*v.climb, -8, 8)
                self.set_pitch(hold, dt, rate=8. if returning else 12.,
                               max_step=8./a.rate if returning else None)
            elif a.actor_handover:
                self.actor_return_slew = True
                # In actor HIL, manual inputs are the fallback setpoints. The Pi
                # uses its explicitly named command schedule during ACTIVE.
                if (now-v.seen.get('ATTITUDE_TARGET', -math.inf) > .2
                        or not all(math.isfinite(x) for x in (v.target_pitch, v.target_thrust))):
                    self.release('actor handover attitude target stale or invalid')
                else:
                    self.pitch_command = v.target_pitch
                    self.sticks[0] = int(round(-1000*clamp(v.target_pitch/self.pitch_scale, -1, 1)))
                    self.sticks[2] = int(round(1000*clamp(v.target_thrust, 0, 1)))
        elif self.state == 'abandon':
            self.sticks = [0, 0, 0, 0]
            if now >= self.next['command'] and v.armed:
                self.next['command'] = now+1
                self.command(mav.MAV_CMD_COMPONENT_ARM_DISARM, 0)
            if not v.armed or elapsed > 5:
                self.release(self.reason)

        if self.state in ('roll', 'climb', 'cruise', 'loiter'):
            if not v.armed:
                self.release('PX4 disarmed')
            elif self.state == 'loiter' and (v.mode, v.sub_mode) != (4, 3):
                self.release('PX4 left AUTO_LOITER')
            elif (self.state != 'loiter' and v.mode not in (STABILIZED, OFFBOARD)
                  and not (self.after_sequence and self.after_sequence.state == 'running')):
                self.release(f'PX4 left Stabilized (mode {v.mode})')
        if self.streaming:
            self.link.send(mav.MAVLink_manual_control_message(TARGET[0], *self.sticks, 0))
        self.report(now)

    def pilot_takeover(self, now):
        v = self.vehicle
        if v.pilot is None or now-v.seen.get('pilot', -math.inf) > .5:
            self.pilot_reference = None
            return False
        if self.pilot_reference is None:
            self.pilot_reference = v.pilot
        return any(abs(p-r) > TAKEOVER_STICK for p, r in zip(v.pilot, self.pilot_reference))

    def report(self, now):
        v = self.vehicle
        throttle = self.sticks[2]/1000
        ready = self.streaming and v.fresh(now) and v.entry_ready(throttle)
        self.ready_since = (self.ready_since or now) if ready else None
        if now >= self.next['status']:
            self.next['status'] = now+.5
            write_json(LOG_DIR/'status.json', snapshot(
                v, now, source='autotakeoff', state=self.state, reason=self.reason,
                session_id=getattr(self.a,'managed_session',None), pid=os.getpid(),
                script_has_sticks=self.streaming, throttle_percent=round(100*throttle, 1),
                pitch_command_deg=round(self.pitch_command, 2),
                offboard_entry_ready=ready,
                offboard_entry_stable_s=round(now-self.ready_since, 1) if ready else 0.,
                after_script=self.after_sequence.name if self.after_sequence else None,
                after_state=self.after_sequence.state if self.after_sequence else 'disabled',
                after_step=self.after_sequence.index if self.after_sequence else None,
                after_reason=self.after_sequence.reason if self.after_sequence else '',
                after_ready_stable_s=round(now-self.after_ready_since, 1) if self.after_ready_since is not None else 0.,
                qgc_joystick_seen=v.pilot is not None and now-v.seen.get('pilot', -math.inf) < .5))
        if now >= self.next['log']:
            self.next['log'] = now+.1
            self.log.writerow([f'{now-self.start:.2f}', self.state, v.mode, int(bool(v.armed)),
                               *(f'{x:.3f}' for x in (v.cas, v.height, v.climb, v.pitch, v.roll)),
                               *self.sticks, int(self.streaming)])
        if now >= self.next['echo']:
            self.next['echo'] = now+2
            print(f'  {self.state:8s} mode={v.mode} armed={v.armed} CAS={v.cas:5.1f} h={v.height:6.1f} '
                  f'climb={v.climb:5.1f} pitch={v.pitch:5.1f} roll={v.roll:5.1f} thr={100*throttle:3.0f}%'
                  + ('  [Offboard entry conditions met]' if ready else ''), flush=True)

    def run(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if not getattr(self.a,'managed',False):(LOG_DIR/'stop').unlink(missing_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        self.start = last = time.monotonic()
        period = 1/self.a.rate
        with (LOG_DIR/f'autotakeoff_{stamp}.csv').open('w', newline='') as f:
            self.log = csv.writer(f)
            self.log.writerow(['t_s', 'state', 'px4_mode', 'armed', 'cas_mps', 'height_m', 'climb_mps',
                               'pitch_deg', 'roll_deg', 'stick_x', 'stick_y', 'stick_z', 'stick_r', 'script_has_sticks'])
            deadline = self.start
            while self.state != 'released':
                now = time.monotonic()
                self.stop = self.stop or (LOG_DIR/'stop').exists()
                self.step(now, clamp(now-last, 0, .1))
                last = now
                deadline = max(deadline+period, now-period)
                time.sleep(max(0, deadline-time.monotonic()))
            self.next.update(status=0., log=0., echo=0.)      # final status and log line
            self.report(time.monotonic())
        print('Sticks released: ' + self.reason, flush=True)
        return 0 if self.reason in ('stop requested', 'QGC sticks moved: pilot has control', 'command script complete') else 2


def open_link(args, record=False):
    capture = None
    if record:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        capture = (LOG_DIR/f'autotakeoff_{time.strftime("%Y%m%d_%H%M%S")}_wire.bin').open('xb')
        header = json.dumps(dict(role='hil_autotakeoff', channels={'1': 'bridge_rx', '5': 'script_tx'},
                                 unix_start_s=time.time(), monotonic_start_s=time.monotonic(), schema=1)).encode()
        capture.write(b'SKTCAP01'+struct.pack('<I', len(header))+header)
    return Link(args.listen_port, args.bridge_port, capture)


def status(args):
    try:
        link = open_link(args)
    except OSError:                    # the port is held by a running takeoff: use what it publishes
        path = LOG_DIR/'status.json'
        if not path.exists() or time.time()-path.stat().st_mtime > 3:
            print(json.dumps(dict(error='agent port busy and no fresh autotakeoff status')))
            return 2
        print(path.read_text(), end='')
        return 0
    vehicle = Vehicle()
    end = time.monotonic()+args.listen
    while time.monotonic() < end:
        now = time.monotonic()
        for message in link.receive():
            vehicle.update(message, now)
        time.sleep(.02)
    link.close()
    now = time.monotonic()
    print(json.dumps(snapshot(vehicle, now, source='listen_only', state='no takeoff script running'), indent=2))
    return 0 if vehicle.fresh(now) else 2


def reboot(args):
    try:
        link = open_link(args)
    except OSError as exc:
        print(f'Agent port {args.listen_port} unavailable ({exc}); stop the running takeoff first', file=sys.stderr)
        return 2
    vehicle = Vehicle()
    mavlink = link.mav

    def listen(seconds, until=lambda: False):
        end = time.monotonic()+seconds
        while time.monotonic() < end and not until():
            now = time.monotonic()
            for message in link.receive():
                vehicle.update(message, now)
            time.sleep(.02)
        return until()

    def heartbeat_age():
        return time.monotonic()-vehicle.seen.get('HEARTBEAT', -math.inf)
    try:
        if not listen(4, lambda: 'HEARTBEAT' in vehicle.seen):
            print('No PX4 heartbeat on the agent port; is the bridge running?')
            return 2
        for _ in range(6):
            if 'SYS_HITL' in vehicle.params:
                break
            link.send(mav.MAVLink_param_request_read_message(*TARGET, b'SYS_HITL', -1))
            listen(.5, lambda: 'SYS_HITL' in vehicle.params)
        if vehicle.params.get('SYS_HITL') != 1:
            print(f'Refusing to reboot: SYS_HITL={vehicle.params.get("SYS_HITL")}')
            return 2
        if vehicle.armed and vehicle.fresh(time.monotonic()):
            print('Refusing to reboot: armed and the model is still running; stop the model first')
            return 2
        if vehicle.armed:              # HIL only, model stopped: nothing is flying any more
            link.send(mav.MAVLink_command_long_message(*TARGET, mav.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, 21196, 0, 0, 0, 0, 0))
            if not listen(5, lambda: not vehicle.armed):
                print('PX4 stayed armed; not rebooting. ' + ' | '.join(vehicle.texts[-2:]))
                return 2
        link.send(mav.MAVLink_command_long_message(*TARGET, mav.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0, 1, 0, 0, 0, 0, 0, 0))
        if not listen(8, lambda: heartbeat_age() > 2.5):
            print('PX4 kept running: reboot not accepted. ' + ' | '.join(vehicle.texts[-2:]))
            return 2
        vehicle.seen.pop('HEARTBEAT')
        if not listen(40, lambda: 'HEARTBEAT' in vehicle.seen):
            print('PX4 went down but no heartbeat has returned yet; check the bridge reconnection')
            return 2
        print(f'PX4 rebooted: heartbeat back, armed={vehicle.armed}, mode={vehicle.mode}')
        return 0
    finally:
        link.close()


def main():
    global LOG_DIR
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('action', choices=['takeoff', 'status', 'stop', 'reboot'])
    p.add_argument('--bridge-port', type=int, default=14576, help='bridge --agent-local-port')
    p.add_argument('--listen-port', type=int, default=14560, help='bridge --agent-destination-port')
    p.add_argument('--takeoff-throttle', type=float, default=.45, help='ground roll and climb, 0-1; SkySurfer initial setting')
    p.add_argument('--cruise-throttle', type=float, default=.35, help='level flight, 0-1; SkySurfer initial setting')
    p.add_argument('--rotate-cas', type=float, default=12., help='m/s; pitch up from this airspeed')
    p.add_argument('--climb-pitch', type=float, default=12., help='deg')
    p.add_argument('--altitude', type=float, default=100., help='m above the EKF local origin')
    p.add_argument('--altitude-gain', type=float, default=.5, help='deg of pitch per m of height error')
    p.add_argument('--climb-damping', type=float, default=1., help='deg of pitch per m/s of climb rate')
    p.add_argument('--rate', type=float, default=50., help='MANUAL_CONTROL rate, Hz')
    p.add_argument('--listen', type=float, default=2.5, help='status: seconds to listen')
    p.add_argument('--record', action='store_true', help='also save the raw MAVLink bytes heard and sent')
    p.add_argument('--actor-handover', action='store_true',
                   help='Offboard: track PX4 pitch/thrust targets with fallback sticks; intended for bounded actor HIL schedules')
    p.add_argument('--after', metavar='SCRIPT', help='run commands/SCRIPT.py after a stable successful takeoff')
    p.add_argument('--after-stable-seconds', type=float, default=3., help='continuous post-takeoff readiness time')
    p.add_argument('--after-timeout', type=float, default=60., help='maximum wait for post-takeoff readiness')
    p.add_argument('--managed',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--validate-only',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--managed-session',help=argparse.SUPPRESS)
    p.add_argument('--start-gate',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--json', action='store_true', help='status: machine-readable JSON (already the default)')
    p.add_argument('--log-dir', type=Path, default=LOG_DIR, help='status.json, stop file and flight logs')
    args = p.parse_args()
    if args.json and args.action != 'status':
        p.error('--json is only supported by status')
    if args.after and args.action != 'takeoff':
        p.error('--after is only supported by takeoff')
    if args.after and args.actor_handover:
        p.error('--after cannot be combined with --actor-handover')
    if not all(math.isfinite(x) and x > 0 for x in (args.after_stable_seconds, args.after_timeout)):
        p.error('post-takeoff readiness timings must be finite and positive')
    if args.after_timeout < args.after_stable_seconds:
        p.error('--after-timeout must be at least --after-stable-seconds')
    args.after_sequence = None
    if args.after:
        try:
            args.after_sequence = load_script(args.after)
        except Exception as exc:
            p.error('cannot load command script: ' + str(exc))
    LOG_DIR = args.log_dir.resolve()
    if not (0 < args.takeoff_throttle <= 1 and 0 < args.cruise_throttle <= 1 and 5 <= args.rotate_cas <= 30
            and 0 < args.climb_pitch <= 25 and 20 <= args.altitude <= 500 and 20 <= args.rate <= 100):
        p.error('flight settings outside the allowed range')
    if not (1 <= args.bridge_port <= 65535 and 1 <= args.listen_port <= 65535
            and args.bridge_port != args.listen_port):
        p.error('bridge/listen ports must be distinct and in 1..65535')
    if not (math.isfinite(args.altitude_gain) and args.altitude_gain > 0
            and math.isfinite(args.climb_damping) and args.climb_damping >= 0
            and math.isfinite(args.listen) and args.listen > 0):
        p.error('altitude gain/listen must be positive; damping nonnegative; all finite')
    if args.validate_only:
        print(json.dumps({'valid':True}))
        return 0
    if bool(args.managed_session) != bool(args.start_gate) or (args.managed_session and not args.managed):
        p.error('managed startup requires session and gate together')
    if args.action == 'status':
        return status(args)
    if args.action == 'reboot':
        return reboot(args)
    if args.action == 'stop':
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR/'stop').touch()
        print('Stop requested')
        return 0
    try:
        link = open_link(args, args.record)
    except OSError as exc:
        print(f'Agent port {args.listen_port} unavailable ({exc}); another takeoff/status is running', file=sys.stderr)
        return 2
    flight = Takeoff(args, link)

    def interrupt(_signum, _frame):
        flight.stop = True
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, interrupt)
    try:
        if args.managed_session:
            # The port is owned, but no flight command is permitted before the
            # parent confirms this session, model run and FC connection.
            LOG_DIR.mkdir(parents=True,exist_ok=True)
            write_json(LOG_DIR/'status.json',dict(session_id=args.managed_session,
                       pid=os.getpid(),state='startup_ready',script_has_sticks=False))
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                if flight.stop or (LOG_DIR/'stop').exists():return 0
                try:gate=json.loads(args.start_gate.read_text())
                except (OSError,ValueError):gate={}
                if gate.get('session_id')==args.managed_session:break
                time.sleep(.02)
            else:
                print('Managed startup gate timeout',file=sys.stderr)
                return 2
        return flight.run()
    finally:
        link.close()


if __name__ == '__main__':
    raise SystemExit(main())

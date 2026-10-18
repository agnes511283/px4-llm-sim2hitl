"""Ticked command sequences sharing the pilot's sole MAVLink link and writer.

Scripts export build_sequence() and ON_FINISH ('hold', 'loiter' or 'release'). Loading and
validation finish before the agent socket is opened. No script owns a socket or
sleeps inside the flight loop; durations are evaluated using monotonic ticks.
"""
from dataclasses import dataclass
import importlib.util
import math
from pathlib import Path
import re


@dataclass(frozen=True)
class Wait:
    seconds: float


@dataclass(frozen=True)
class Mode:
    main_mode: int
    sub_mode: int = 0
    timeout: float = 5.


@dataclass(frozen=True)
class Sticks:
    """Raw normalized MANUAL_CONTROL x/y/z/r, not angles in degrees."""
    pitch: float
    roll: float
    throttle: float
    seconds: float
    yaw: float = 0.


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def validate(actions):
    for action in actions:
        if isinstance(action, Wait):
            if not positive(action.seconds):
                raise ValueError('Wait.seconds must be finite and positive')
        elif isinstance(action, Mode):
            # 6 = OFFBOARD: PX4 enters it only while a source sends the offboard signal (a module of modules/, e.g.
            # sks_template) and leaves it through its own offboard-loss failsafe when the signal stops.
            if (type(action.main_mode) is not int or action.main_mode not in (1, 2, 3, 4, 5, 6, 7, 8)
                    or type(action.sub_mode) is not int or not 0 <= action.sub_mode <= 255
                    or not positive(action.timeout)):
                raise ValueError('Mode requires a supported main mode, submode 0..255 and positive timeout')
        elif isinstance(action, Sticks):
            values = (action.pitch, action.roll, action.yaw, action.throttle)
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in values):
                raise ValueError('stick values must be finite numbers')
            if not (all(-1 <= x <= 1 for x in values[:3]) and 0 <= action.throttle <= 1 and positive(action.seconds)):
                raise ValueError('pitch/roll/yaw must be -1..1, throttle 0..1, seconds positive')
        else:
            raise ValueError('unsupported command action: ' + type(action).__name__)


def load_script(name):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError('--after must be a script name inside hitl/commands (without .py)')
    if name in ('sequence', '__init__'):
        raise ValueError('select a command script, not a helper module')
    path = Path(__file__).resolve().parent/(name + '.py')
    if not path.is_file() or path.resolve().parent != Path(__file__).resolve().parent:
        raise ValueError('command script not found: ' + name)
    spec = importlib.util.spec_from_file_location('commands._selected_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'build_sequence', None)):
        raise ValueError('command script must export build_sequence()')
    actions = tuple(module.build_sequence())
    validate(actions)
    finish = getattr(module, 'ON_FINISH', None)
    if finish not in ('hold', 'loiter', 'release'):
        raise ValueError('ON_FINISH must be hold, loiter or release')
    return CommandSequence(name, actions, finish)


class CommandSequence:
    def __init__(self, name, actions, finish='hold'):
        self.name, self.actions, self.finish = name, tuple(actions), finish
        validate(self.actions)
        if finish not in ('hold', 'loiter', 'release'):
            raise ValueError('invalid finish policy')
        self.state = 'waiting'
        self.index = 0
        self.started = self.next_mode_command = None
        self.reason = ''
        self.expected_mode = (7, 0)

    def begin(self):
        if self.state != 'waiting':
            raise RuntimeError('command script can only start once')
        self.state = 'running'

    def cancel(self, reason):
        if self.state in ('waiting', 'running'):
            self.state, self.reason = 'cancelled', reason

    def tick(self, flight, now):
        if self.state != 'running':
            return
        if self.index >= len(self.actions):
            self.state = 'complete'
            if self.finish == 'release':
                flight.release('command script complete')
            elif self.finish == 'loiter':
                if (flight.vehicle.mode, flight.vehicle.sub_mode) != (4, 3):
                    self.state, self.reason = 'failed', 'loiter requires PX4 AUTO_LOITER'
                    flight.release(self.reason)
                else:
                    # FW AUTO ignores sticks, but the configured RC-loss failsafe
                    # still needs manual-input availability. PX4 owns navigation.
                    flight.sticks[:] = [0, 0, round(1000*flight.a.cruise_throttle), 0]
                    flight.pitch_command = 0.
                    flight.go('loiter', 'PX4 AUTO_LOITER confirmed; neutral input keepalive')
            elif flight.vehicle.mode != 7:
                self.state, self.reason = 'failed', 'hold requires Stabilized at the end of the script'
                flight.release(self.reason)
            else:
                flight.sticks[1] = flight.sticks[3] = 0
            return
        action = self.actions[self.index]
        if self.started is None:
            self.started, self.next_mode_command = now, now
        complete = False
        current_mode = (flight.vehicle.mode, getattr(flight.vehicle, 'sub_mode', 0))
        allowed = {self.expected_mode}
        if isinstance(action, Mode):
            allowed.add((action.main_mode, action.sub_mode))
        if current_mode not in allowed:
            self.state, self.reason = 'failed', 'PX4 mode changed outside the command sequence'
            flight.release(self.reason)
            return
        if isinstance(action, Mode):
            complete = (flight.vehicle.mode == action.main_mode
                        and getattr(flight.vehicle, 'sub_mode', 0) == action.sub_mode)
            if not complete:
                if now-self.started >= action.timeout:
                    self.state, self.reason = 'failed', 'mode change timed out'
                    flight.release(self.reason)
                    return
                if now >= self.next_mode_command:
                    self.next_mode_command = now+1.
                    flight.command(flight.mode_command_id, 1, action.main_mode, action.sub_mode)
        elif isinstance(action, Sticks):
            flight.sticks[:] = [round(1000*action.pitch), round(1000*action.roll),
                               round(1000*action.throttle), round(1000*action.yaw)]
            flight.pitch_command = -action.pitch*flight.pitch_scale
            complete = now-self.started >= action.seconds
        else:  # Wait: keep the last sticks while the regular writer keeps streaming.
            complete = now-self.started >= action.seconds
        if complete:
            if isinstance(action, Mode):
                self.expected_mode = (action.main_mode, action.sub_mode)
            self.index += 1
            self.started = None

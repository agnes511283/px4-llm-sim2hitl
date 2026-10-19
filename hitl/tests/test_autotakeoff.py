"""Pilot state-machine checks without sockets, files, models or hardware."""
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

path = Path(__file__).resolve().parents[1] / 'autotakeoff/autotakeoff.py'
spec = importlib.util.spec_from_file_location('autotakeoff_pilot', path)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def flight(self):
        args = SimpleNamespace(takeoff_throttle=.45, cruise_throttle=.35, rotate_cas=12.,
                               climb_pitch=12., altitude=100., altitude_gain=.5,
                               climb_damping=1., rate=50., actor_handover=False)
        link = Mock()
        link.receive.return_value = []
        t = pilot.Takeoff(args, link)
        t.report = Mock()
        t.next['heartbeat'] = math.inf
        v = t.vehicle
        v.mode = pilot.STABILIZED
        v.armed = False
        v.vehicle_type = pilot.mav.MAV_TYPE_FIXED_WING
        v.cas = v.height = v.climb = v.pitch = v.roll = 0.
        v.params = {'SYS_HITL': 1, 'FW_MAN_P_MAX': 30.}
        v.seen = {key: 10. for key in ('HEARTBEAT', 'VFR_HUD', 'LOCAL_POSITION_NED', 'ATTITUDE')}
        t.state, t.since = 'check', 10.
        return t

    def test_non_hil_refuses_without_arm_or_sticks(self):
        t = self.flight()
        t.vehicle.params['SYS_HITL'] = 0
        t.step(10., .02)
        self.assertEqual(t.state, 'released')
        self.assertFalse(t.streaming)
        sent = [call.args[0].get_type() for call in t.link.send.call_args_list]
        self.assertNotIn('COMMAND_LONG', sent)
        self.assertNotIn('MANUAL_CONTROL', sent)

    def test_already_flying_refuses(self):
        t = self.flight()
        t.vehicle.cas = 16.
        t.step(10., .02)
        self.assertEqual(t.state, 'released')
        self.assertFalse(t.streaming)

    def test_invalid_pitch_scale_refuses(self):
        for scale in (0., -1., math.nan, math.inf):
            with self.subTest(scale=scale):
                t = self.flight()
                t.vehicle.params['FW_MAN_P_MAX'] = scale
                t.step(10., .02)
                self.assertEqual(t.state, 'released')
                self.assertFalse(t.streaming)

    def test_mode_changes_once_flying_keep_the_sticks(self):
        """cruise -> OFFBOARD -> AUTO_LOITER -> OFFBOARD -> AUTO_LOITER -> Stabilized -> Position, RTL, OFFBOARD:
        MANUAL_CONTROL goes on all the time (in HITL these sticks are PX4's RC; a gap trips the RC-loss failsafe)"""
        t = self.flight()
        t.vehicle.armed, t.vehicle.cas, t.vehicle.height = True, 18., 100.
        t.airborne, t.streaming, t.state = True, True, 'cruise'
        v = t.vehicle
        sent = lambda: sum(1 for c in t.link.send.call_args_list if c.args[0].get_type() == 'MANUAL_CONTROL')
        for mode, sub, state in ((pilot.OFFBOARD, 0, 'cruise'), (4, 3, 'loiter'), (pilot.OFFBOARD, 0, 'loiter'),
                                 (4, 3, 'loiter'), (pilot.STABILIZED, 0, 'cruise'), (3, 0, 'loiter'), (4, 5, 'loiter'),
                                 (pilot.OFFBOARD, 0, 'loiter')):
            v.mode, v.sub_mode = mode, sub
            before = sent()
            t.step(10., .02)
            t.step(10., .02)
            self.assertEqual(t.state, state, (mode, sub))
            self.assertTrue(t.streaming)
            self.assertEqual(sent(), before + 2)
            if state == 'loiter':
                self.assertEqual(t.sticks, [0, 0, round(1000 * .35), 0])
        t.stop, t.stop_reason = True, 'stop-takeoff'                # an explicit stop still hands back
        t.step(10., .02)
        self.assertEqual(t.state, 'released')
        self.assertFalse(t.streaming)

    def test_mode_change_during_the_takeoff_still_stops(self):
        t = self.flight()
        t.vehicle.armed, t.vehicle.cas, t.vehicle.height = True, 14., 20.
        t.airborne, t.streaming, t.state = True, True, 'climb'
        t.vehicle.mode, t.vehicle.sub_mode = 4, 3
        t.step(10., .02)
        self.assertEqual(t.state, 'released')

    def test_ground_to_cruise_and_default_offboard_behavior(self):
        t = self.flight()
        t.step(10., .02)
        self.assertEqual(t.state, 'mode')
        t.since = 8.
        t.step(10., .02)
        self.assertEqual(t.state, 'arm')
        t.vehicle.armed = True
        t.step(10., .02)
        self.assertEqual(t.state, 'roll')
        t.vehicle.cas = 12.
        t.step(10., .02)
        self.assertEqual(t.state, 'climb')
        t.vehicle.height = 100.
        t.step(10., .02)
        self.assertEqual(t.state, 'cruise')
        t.vehicle.mode = pilot.OFFBOARD
        sticks = t.sticks.copy()
        t.step(10., .02)
        self.assertEqual(t.sticks, sticks)

    def test_qgc_movement_releases_sticks(self):
        t = self.flight()
        t.state = 'cruise'
        t.streaming = True
        t.vehicle.armed = True
        t.vehicle.pilot = (0, 0, 350, 0)
        t.vehicle.seen['pilot'] = 10.
        t.step(10., .02)
        t.vehicle.pilot = (0, 0, 550, 0)
        t.step(10.02, .02)
        self.assertEqual(t.state, 'released')
        self.assertFalse(t.streaming)

    def test_ground_stop_zeros_sticks_and_disarms(self):
        t = self.flight()
        t.state = 'roll'
        t.streaming = True
        t.vehicle.armed = True
        t.sticks = [0, 0, 450, 0]
        t.stop = True
        t.step(10., .02)
        self.assertEqual(t.state, 'abandon')
        t.step(10.02, .02)
        self.assertEqual(t.sticks, [0, 0, 0, 0])
        commands = [c.args[0] for c in t.link.send.call_args_list if c.args[0].get_type() == 'COMMAND_LONG']
        self.assertEqual(commands[-1].command, pilot.mav.MAV_CMD_COMPONENT_ARM_DISARM)
        self.assertEqual(commands[-1].param1, 0)

    def test_airborne_telemetry_loss_releases(self):
        t = self.flight()
        t.state = 'cruise'
        t.streaming = t.airborne = True
        t.vehicle.armed = True
        t.vehicle.seen['ATTITUDE'] = 0.
        t.step(10., .02)
        self.assertEqual(t.state, 'released')
        self.assertEqual(t.reason, 'telemetry lost')

    def test_invalid_telemetry_cannot_start_takeoff(self):
        for field in ('cas', 'height', 'climb', 'pitch', 'roll'):
            with self.subTest(field=field):
                t = self.flight()
                t.state = 'connect'
                setattr(t.vehicle, field, math.nan)
                t.step(10., .02)
                self.assertEqual(t.state, 'connect')
                self.assertFalse(t.streaming)


if __name__ == '__main__':
    unittest.main()

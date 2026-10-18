"""Script trigger, ownership, mode feedback, cancellation; no hardware/sockets."""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from commands.sequence import CommandSequence, Mode, Sticks, Wait, load_script, validate
import commands.sequence as sequence_module

spec = importlib.util.spec_from_file_location('command_pilot', ROOT/'autotakeoff/FW_SkySurfer_HIL_AutoTakeoff.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class CommandTests(unittest.TestCase):
    def flight(self, actions=(), finish='hold'):
        args = SimpleNamespace(takeoff_throttle=.45, cruise_throttle=.35, rotate_cas=12.,
                               climb_pitch=12., altitude=100., altitude_gain=.5, climb_damping=1.,
                               rate=50., actor_handover=False, after_stable_seconds=3., after_timeout=60.,
                               after_sequence=CommandSequence('test', actions, finish))
        link = Mock()
        link.receive.return_value = []
        t = pilot.Takeoff(args, link)
        t.report = Mock()
        t.next['heartbeat'] = math.inf
        t.state, t.since = 'cruise', 10.
        t.streaming = t.airborne = True
        v = t.vehicle
        v.mode, v.sub_mode, v.armed = 7, 0, True
        v.height, v.cas, v.climb, v.pitch, v.roll = 100., 15., 0., 0., 0.
        t.sticks[:] = [0, 0, 350, 0]
        self.fresh(t, 10.)
        return t

    def fresh(self, t, now):
        for key in ('HEARTBEAT', 'VFR_HUD', 'LOCAL_POSITION_NED', 'ATTITUDE'):
            t.vehicle.seen[key] = now

    def tick(self, t, now):
        self.fresh(t, now)
        t.step(now, .02)

    def test_template_has_no_commands(self):
        script = load_script('after_takeoff_template')
        self.assertEqual(script.actions, ())
        self.assertEqual(script.finish, 'hold')

    def test_stable_readiness_triggers_once_not_a_fixed_delay(self):
        t = self.flight([Wait(1.)])
        t.vehicle.height = 50.
        self.tick(t, 10.)
        self.tick(t, 20.)
        self.assertEqual(t.after_sequence.state, 'waiting')
        t.vehicle.height = 100.
        self.tick(t, 21.)
        self.tick(t, 23.9)
        self.assertEqual(t.after_sequence.state, 'waiting')
        self.tick(t, 24.)
        self.assertEqual(t.after_sequence.state, 'running')
        self.tick(t, 25.)
        self.tick(t, 25.02)
        self.assertEqual(t.after_sequence.state, 'complete')
        self.tick(t, 30.)
        self.assertEqual(t.after_sequence.state, 'complete')

    def test_unstable_interval_resets_readiness(self):
        t = self.flight([Wait(1.)])
        self.tick(t, 10.)
        t.vehicle.roll = 10.
        self.tick(t, 12.)
        t.vehicle.roll = 0.
        self.tick(t, 13.)
        self.tick(t, 15.)
        self.assertEqual(t.after_sequence.state, 'waiting')
        self.tick(t, 16.)
        self.assertEqual(t.after_sequence.state, 'running')

    def test_climb_timeout_cannot_run_script(self):
        t = self.flight([Sticks(.1, .1, .35, 2.)])
        t.climb_timed_out = True
        self.tick(t, 10.)
        self.assertEqual(t.after_sequence.state, 'failed')
        self.assertEqual(t.state, 'released')
        self.assertFalse(t.streaming)

    def test_readiness_timeout_is_reported(self):
        t = self.flight([Wait(1.)])
        t.vehicle.height = 50.
        self.tick(t, 10.)
        self.tick(t, 70.)
        self.assertEqual(t.after_sequence.state, 'failed')
        self.assertIn('readiness timed out', t.reason)

    def test_script_owns_sticks_and_does_not_open_another_link(self):
        t = self.flight([Sticks(-.1, .2, .4, 2.)])
        with patch.object(pilot, 'open_link', side_effect=AssertionError('second link')):
            self.tick(t, 10.)
            self.tick(t, 13.)
            self.assertEqual(t.sticks, [-100, 200, 400, 0])
            self.tick(t, 14.)
            self.assertEqual(t.sticks, [-100, 200, 400, 0])
        # Exactly one MANUAL_CONTROL per tick: the existing flight writer.
        messages = [c.args[0] for c in t.link.send.call_args_list if c.args[0].get_type() == 'MANUAL_CONTROL']
        self.assertEqual(len(messages), 3)

    def test_mode_change_waits_for_heartbeat_and_uses_same_writer(self):
        t = self.flight([Mode(2), Sticks(0, .1, .35, 1.)], 'release')
        self.tick(t, 10.)
        self.tick(t, 13.)
        self.assertEqual(t.after_sequence.index, 0)
        commands = [c.args[0] for c in t.link.send.call_args_list if c.args[0].get_type() == 'COMMAND_LONG']
        self.assertEqual(len(commands), 1)
        self.assertEqual((commands[0].param1, commands[0].param2), (1, 2))
        t.vehicle.mode = 2
        self.tick(t, 13.02)
        self.assertEqual(t.after_sequence.index, 1)
        self.tick(t, 13.04)
        self.assertEqual(t.sticks[1], 100)
        self.assertTrue(t.streaming)

    def test_mode_change_timeout_releases(self):
        t = self.flight([Mode(2, timeout=1.)])
        self.tick(t, 10.)
        self.tick(t, 13.)
        self.tick(t, 14.)
        self.assertEqual(t.after_sequence.state, 'failed')
        self.assertFalse(t.streaming)

    def test_disarm_prevents_mode_command_on_the_same_tick(self):
        t = self.flight([Mode(2)])
        self.tick(t, 10.)
        t.vehicle.armed = False
        self.tick(t, 13.)
        self.assertEqual(t.after_sequence.state, 'cancelled')
        self.assertFalse(any(c.args[0].get_type() == 'COMMAND_LONG' for c in t.link.send.call_args_list))

    def test_unrequested_mode_change_stops_sequence(self):
        t = self.flight([Wait(5.)])
        self.tick(t, 10.)
        self.tick(t, 13.)
        t.vehicle.mode = 6
        self.tick(t, 13.02)
        self.assertEqual(t.after_sequence.state, 'failed')
        self.assertFalse(t.streaming)

    def test_stop_telemetry_loss_and_pilot_takeover_cancel_sequence(self):
        for reason in ('stop', 'telemetry', 'pilot'):
            with self.subTest(reason=reason):
                t = self.flight([Wait(5.)])
                self.tick(t, 10.)
                t.vehicle.pilot, t.vehicle.seen['pilot'] = (0, 0, 350, 0), 13.
                self.tick(t, 13.)
                if reason == 'stop': t.stop = True
                elif reason == 'telemetry': t.vehicle.seen['ATTITUDE'] = 0.
                else:
                    t.vehicle.pilot, t.vehicle.seen['pilot'] = (0, 200, 350, 0), 13.02
                t.step(13.02, .02)
                self.assertEqual(t.after_sequence.state, 'cancelled')
                self.assertFalse(t.streaming)

    def test_empty_template_continues_hold_without_mode_commands(self):
        t = self.flight()
        self.tick(t, 10.)
        self.tick(t, 13.)
        self.assertEqual(t.after_sequence.state, 'complete')
        self.assertTrue(t.streaming)
        self.assertFalse(any(c.args[0].get_type() == 'COMMAND_LONG' for c in t.link.send.call_args_list))

    def test_finish_requires_explicit_hold_or_release(self):
        t = self.flight([], 'release')
        self.tick(t, 10.)
        self.tick(t, 13.)
        self.assertEqual(t.reason, 'command script complete')
        self.assertFalse(t.streaming)
        t = self.flight([Mode(2)])
        self.tick(t, 10.)
        self.tick(t, 13.)
        t.vehicle.mode = 2
        self.tick(t, 13.02)
        self.tick(t, 13.04)
        self.assertEqual(t.after_sequence.state, 'failed')

    def test_offboard_allowed_and_template_script_loads(self):
        # OFFBOARD (6) is allowed since a module of modules/ can send the offboard signal; PX4 refuses it otherwise.
        validate([Mode(6, 0, timeout=8.)])
        script = load_script('template_offboard')
        self.assertIn(Mode(6, 0, timeout=8.), script.actions)
        self.assertEqual(script.finish, 'loiter')

    def test_bad_actions_rejected_before_flight(self):
        for action in (Mode(9), Mode(7, timeout=math.inf), Sticks(2, 0, .35, 1),
                       Sticks(0, 0, -1, 1), Wait(0), Wait(math.nan), object()):
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate([action])

    def test_loader_rejects_missing_or_invalid_scripts(self):
        for name in ('../escape', 'missing_script', 'sequence', 'bad.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_script(name)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'bad.py').write_text('def build_sequence(): return []\nON_FINISH="undefined"\n')
            with patch.object(sequence_module, '__file__', str(root/'sequence.py')):
                with self.assertRaisesRegex(ValueError, 'ON_FINISH'):
                    load_script('bad')


    def test_loiter_script_confirms_auto_submode_then_releases(self):
        script=load_script('after_takeoff_loiter')
        self.assertEqual(script.actions,(Mode(4,3,timeout=8.),))
        self.assertEqual(script.finish,'loiter')
        t=self.flight(script.actions,'loiter')
        self.tick(t,10.);self.tick(t,13.)
        command=[c.args[0] for c in t.link.send.call_args_list if c.args[0].get_type()=='COMMAND_LONG'][-1]
        self.assertEqual((command.param2,command.param3),(4,3))
        t.vehicle.mode,t.vehicle.sub_mode=4,4
        self.tick(t,13.02)
        self.assertEqual(t.after_sequence.state,'failed')
        t=self.flight(script.actions,'loiter')
        self.tick(t,10.);self.tick(t,13.)
        t.vehicle.mode,t.vehicle.sub_mode=4,3
        self.tick(t,13.02);self.tick(t,13.04)
        self.assertEqual(t.after_sequence.state,'complete')
        self.assertEqual(t.state,'loiter')
        self.assertTrue(t.streaming)
        self.assertEqual(t.sticks[:],[0,0,350,0])
        self.tick(t,13.06)
        self.assertEqual(t.state,'loiter')
        self.assertTrue(t.streaming)
        t.stop=True;self.tick(t,13.08)
        self.assertFalse(t.streaming)

    def test_stabilized_steps_follows_the_sitl_scenario_then_loiters(self):
        script = load_script('stabilized_steps')
        self.assertEqual(script.finish, 'loiter')
        self.assertEqual(script.actions[-1], Mode(4, 3, timeout=8.))
        sticks = script.actions[:-1]
        self.assertAlmostEqual(sum(a.seconds for a in sticks), 80.)
        t = self.flight(script.actions, 'loiter')
        sent = {}
        now = 10.
        while t.after_sequence.state in ('waiting', 'running') and now < 100.:
            self.tick(t, now)
            sent[round(now - 13., 2)] = tuple(t.sticks)  # the sequence starts at 13 s (3 s readiness)
            if t.after_sequence.index == len(script.actions) - 1:
                t.vehicle.mode, t.vehicle.sub_mode = 4, 3
            now += .02
        self.assertEqual(t.after_sequence.state, 'complete')
        self.assertEqual(t.state, 'loiter')
        base = (-125, 0, 115, 0)
        for when, expected in ((1., base), (64.5, (-125, 500, 115, 0)), (67.5, base),
                               (70., (175, 0, 115, 0)), (72.5, base), (75., (-125, 0, 115, 500)), (78., base)):
            self.assertEqual(sent[when], expected, when)


if __name__ == '__main__':
    unittest.main()

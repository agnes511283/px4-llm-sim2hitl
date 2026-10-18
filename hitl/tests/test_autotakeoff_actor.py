"""Offline tests of actor HIL fallback-stick tracking; no ports or hardware."""
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

source=Path(__file__).resolve().parents[1]/'autotakeoff/autotakeoff.py'
spec=importlib.util.spec_from_file_location('autotakeoff_actor',source)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class HandoverTests(unittest.TestCase):
    def takeoff(self):
        args=SimpleNamespace(actor_handover=True,cruise_throttle=.5,altitude_gain=.5,
                             altitude=100.,climb_damping=1.,rate=50.)
        link=Mock();link.receive.return_value=[]
        t=m.Takeoff(args,link);t.state='cruise';t.streaming=True
        t.report=Mock();t.next['heartbeat']=math.inf
        v=t.vehicle;v.mode=6;v.armed=True;v.height=100.;v.climb=0.;v.cas=20.;v.pitch=-2.;v.roll=0.
        for kind in ('HEARTBEAT','VFR_HUD','LOCAL_POSITION_NED','ATTITUDE','ATTITUDE_TARGET'):v.seen[kind]=10.
        v.target_pitch=-3.2;v.target_thrust=.57
        return t

    def test_offboard_sticks_match_px4_pitch_and_thrust_targets(self):
        t=self.takeoff();t.step(10.,.02)
        self.assertEqual(t.sticks,[107,0,570,0])
        self.assertAlmostEqual(t.pitch_command,-3.2)

    def test_return_resumes_actor_slew_limits(self):
        t=self.takeoff();t.step(10.,.02);t.vehicle.mode=7;t.step(10.02,.02)
        self.assertAlmostEqual(t.pitch_command,-3.04)
        self.assertEqual(t.sticks[2],565)

    def test_late_return_tick_cannot_increase_command_step(self):
        t=self.takeoff();t.step(10.,.02);t.vehicle.mode=7;t.step(10.08,.08)
        self.assertAlmostEqual(t.pitch_command,-3.04)
        self.assertEqual(t.sticks[2],565)

    def test_initial_stabilized_cruise_retains_original_slew(self):
        t=self.takeoff();t.vehicle.mode=7;t.pitch_command=-3.2;t.sticks[2]=570
        t.step(10.,.02)
        self.assertAlmostEqual(t.pitch_command,-2.96)
        self.assertEqual(t.sticks[2],560)

    def test_stale_target_releases_sticks(self):
        t=self.takeoff();t.vehicle.seen['ATTITUDE_TARGET']=9.
        t.step(10.,.02);self.assertFalse(t.streaming)
        self.assertEqual(t.state,'released')

    def test_default_behavior_retains_frozen_sticks(self):
        t=self.takeoff();t.a.actor_handover=False;t.sticks=[80,0,500,0]
        t.step(10.,.02);self.assertEqual(t.sticks,[80,0,500,0])

if __name__=='__main__':unittest.main()

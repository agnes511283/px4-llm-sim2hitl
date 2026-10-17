"""Flight-test defaults and overrides, preflight and flight-summary; no FC or serial."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

RUNTIME = Path(__file__).resolve().parents[1]
PROJECT = RUNTIME.parent
sys.path.insert(0, str(RUNTIME))
from host import flight_config, agent_tools


def flight_args(**overrides):
    values = dict(flight_config.config()['flight_test'], fake_fc=False, fake_state_dir=None, log_dir=None)
    values.update(overrides)
    return SimpleNamespace(**values)


class FlightConfigTests(unittest.TestCase):
    def test_config_shape(self):
        config = flight_config.config()
        for key in ['altitude', 'hold_seconds', 'hold_timeout', 'flight_timeout']:
            self.assertGreater(config['flight_test'][key], 0)
        self.assertIn('late_steps_max', config['pass_criteria'])


class FlightOverrideTests(unittest.TestCase):
    def test_standard_flight_has_no_overrides(self):
        self.assertEqual(flight_config.flight_test_overrides(flight_args()), {})

    def test_nonstandard_flight_lists_overrides(self):
        overrides = flight_config.flight_test_overrides(flight_args(altitude=300))
        self.assertEqual(overrides, {'altitude': (300, 100)})

    def test_fake_fc_flight_checks_its_arguments(self):
        from host.flight_test import run_test

        args = flight_args(altitude=300, hold_timeout=1, hold_seconds=2)
        args.fake_fc = True
        with self.assertRaises(ValueError):
            run_test(RUNTIME, args)


class ToolTests(unittest.TestCase):
    def make_run(self, folder, **changes):
        folder = Path(folder)
        (folder / 'host').mkdir(parents=True)
        result = {
            'status': 'PASS',
            'flight': 'PASS',
            'recovery': 'PASS',
            'flight_seconds': 90.0,
            'hold_seconds': 60.1,
            'orbit': {'turns': 2.7, 'radius_m': 78.0, 'radius_std_m': 9.0, 'height_min_m': 101.0, 'height_max_m': 114.0, 'airspeed_min_m_s': 17.0},
            'last_flight_status': {
                'build_id': 'b',
                'runtime_identity': {'source_id': 'r'},
                'metrics': {'serial_errors': 0, 'native_log_drops': 0, 'serial_max_write_ms': 1.0},
            },
        }
        result.update(changes.pop('result', {}))
        final = {'recovery': 'complete', 'recovery_required': False, 'fc': {'armed': False, 'SYS_HITL': 1}, 'recovery_details': {'force_disarm_used': True}}
        final.update(changes.pop('final', {}))
        (folder / 'result.json').write_text(json.dumps(result))
        (folder / 'host/final_status.json').write_text(json.dumps(final))
        rows = ['%d,10000,%d,0' % (i, changes.get('late_ns', 20000) if i == 5 else 20000) for i in range(100)]
        (folder / 'host/timing.csv').write_text('\n'.join(rows) + '\n')
        return folder

    def test_summary_pass_and_baseline_compare(self):
        with tempfile.TemporaryDirectory() as d:
            value = agent_tools.flight_summary(self.make_run(d))
            self.assertEqual(value['verdict'], 'PASS', value['failures'])
            self.assertEqual(value['timing']['late_steps'], 0)
            self.assertIn('hold_seconds', value['baseline_compare'])
            self.assertTrue(value['notes'])

    def test_summary_fails_on_late_step_short_hold_and_pending(self):
        with tempfile.TemporaryDirectory() as d:
            folder = self.make_run(d, late_ns=5_000_000, result={'hold_seconds': 30.0}, final={'recovery_required': True})
            value = agent_tools.flight_summary(folder)
            self.assertEqual(value['verdict'], 'FAIL')
            text = ' '.join(value['failures'])
            for needle in ['late', 'hold shorter', 'not confirmed recovered']:
                self.assertIn(needle, text)

    def test_summary_with_shared_owner_reads_only_this_test(self):
        # An existing GUI owner: its own log directory, no final_status.json, timing.csv with other runs around.
        with tempfile.TemporaryDirectory() as d:
            owner = Path(d) / 'owner_logs'
            owner.mkdir()
            before = '0,10000,9000000,0\n'  # a late step of an earlier run
            ours = ''.join('%d,10000,20000,0\n' % i for i in range(100))
            after = '0,10000,8000000,0\n'  # and of a later one
            (owner / 'timing.csv').write_text(before + ours + after)
            start = len(before.encode())
            recovered = {'recovery': 'complete', 'recovery_required': False, 'fc': {'armed': False, 'SYS_HITL': 1},
                         'recovery_details': {'force_disarm_used': False}}
            folder = self.make_run(Path(d) / 'test', result={
                'host_log': {'dir': str(owner), 'shared_owner': True, 'timing_start': start,
                             'timing_end': start + len(ours.encode())},
                'after_recovery': recovered})
            (folder / 'host/final_status.json').unlink()
            value = agent_tools.flight_summary(folder)
            self.assertEqual(value['verdict'], 'PASS', value['failures'])
            self.assertEqual((value['timing']['steps'], value['timing']['late_steps']), (100, 0))
            self.assertEqual(value['ending_source'], 'result.json after_recovery')
            self.assertEqual(value['host_log'], str(owner))

    def test_summary_fails_on_incomplete_timing(self):
        # Missing timing evidence is a failure, not zero late steps: empty, a gap, or fewer rows than steps run.
        for rows, expected, needle in [([], 100, 'timing log empty'),
                                       ([0, 1, 2, 4], 4, 'not consecutive'),
                                       (list(range(50)), 100, 'the model produced 100')]:
            with tempfile.TemporaryDirectory() as d:
                folder = self.make_run(d, result={'after_model_stop': {'produced_steps': expected}})
                (folder / 'host/timing.csv').write_text(''.join('%d,10000,20000,0\n' % i for i in rows))
                value = agent_tools.flight_summary(folder)
                self.assertEqual(value['verdict'], 'FAIL')
                self.assertTrue(any(needle in f for f in value['failures']), value['failures'])

    def test_summary_fails_when_app_nap_guard_was_not_held(self):
        with tempfile.TemporaryDirectory() as d:
            folder = self.make_run(d, result={'after_model_stop': {'scheduler': {'activity_run_ok': False}}})
            value = agent_tools.flight_summary(folder)
            self.assertEqual(value['verdict'], 'FAIL')
            self.assertIn('App Nap guard not held during the run', value['failures'])

    def test_preflight_fake_state_without_owner(self):
        with tempfile.TemporaryDirectory() as d:
            value = agent_tools.preflight(RUNTIME, fake_state_dir=Path(d))
            names = {c['name']: c for c in value['checks']}
            self.assertNotIn('serial_device', names)  # fake state never inspects serial
            self.assertTrue(names['no_active_run']['ok'])
            self.assertFalse(names['recovery_marker']['detail']['pending'])
            self.assertTrue(value['ready'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

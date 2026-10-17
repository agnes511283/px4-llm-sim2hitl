"""Direct pilot/JSON/stop; native owner/IPC tested in hil_runtime/tests with a localhost fake PX4, no bridge or model.

Fast telemetry transitions check orchestration only, not aircraft dynamics.
The command fixture lives in a disposable project copy, never the real project.
"""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from autotakeoff_fake_vehicle import FakeVehicle

ROOT = Path(__file__).resolve().parents[1]


class FastVehicle(FakeVehicle):
    def physics(self, dt):
        if not self.armed:
            self.v = self.h = self.theta = self.gamma = 0.
            return
        self.v = min(15., self.v+40*dt)
        self.theta = math.radians(-30*self.sticks[0]/1000)
        if self.v >= 12 and self.theta > math.radians(2):
            self.h = min(100., self.h+150*dt)
        if self.h >= 100:
            self.theta = 0.
        self.gamma = 0.


@unittest.skipUnless(sys.platform == 'darwin', 'native runbridge.command protocol check')
class EntryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='flight protocol 專案 ')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)/'project'
        shutil.copytree(ROOT, self.project/'hil_bridge')
        shutil.copy2(ROOT.parent/'runbridge.command', self.project/'runbridge.command')
        self.entry = self.project/'hil_bridge/autotakeoff/FW_SkySurfer_HIL_AutoTakeoff.py'
        self.folder = Path(self.temp.name)/'flight logs'
        self.env = {**os.environ, 'FW_HIL_PYTHON': sys.executable}
        self.fc = FastVehicle()
        self.fc.start()
        self.addCleanup(self.close_vehicle)
        self.common = ['--bridge-port', str(self.fc.port), '--listen-port', str(self.fc.script_port),
                       '--log-dir', str(self.folder)]
        self.process = None
        self.addCleanup(self.close_process)

    def close_vehicle(self):
        self.fc.running = False
        self.fc.join(timeout=2)
        self.fc.sock.close()

    def close_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.communicate()

    def status_file(self):
        try:
            return json.loads((self.folder/'status.json').read_text())
        except (OSError, ValueError):
            return {}

    def wait(self, condition, seconds=12):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if condition():
                return
            if self.process and self.process.poll() is not None:
                self.fail('pilot ended early: '+self.process.communicate()[0])
            time.sleep(.03)
        self.fail('timed out: '+str(self.status_file()))

    def launch(self, script):
        command = [sys.executable,'-B',str(self.entry), 'takeoff', *self.common, '--after', script,
                   '--after-stable-seconds', '1.', '--after-timeout', '10']
        self.process = subprocess.Popen(command, env=self.env, cwd=Path(self.temp.name),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def run_command(self, *args):
        args=list(args);args[0]='stop' if args[0]=='stop-takeoff' else args[0]
        return subprocess.run([sys.executable,'-B',str(self.entry), *args, *self.common], env=self.env,
                              cwd=Path(self.temp.name), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=6)

    def test_after_commands_flow_through_entry_and_same_agent(self):
        fixture = self.project/'hil_bridge/commands/protocol_fixture.py'
        fixture.write_text("from commands.sequence import Mode, Sticks, Wait\n"
                           "ON_FINISH='release'\n"
                           "def build_sequence(): return [Mode(7), Sticks(-.05,.1,.4,.4), Wait(.1)]\n")
        self.launch('protocol_fixture')
        output = self.process.communicate(timeout=12)[0]
        self.assertEqual(self.process.returncode, 0, output)
        self.assertEqual(self.status_file()['after_state'], 'complete')
        self.assertTrue(any(sticks == (-50, 100, 400, 0) for _, sticks in self.fc.manual))
        self.assertEqual(len({c[0] for c in self.fc.commands}), 2)  # mode/arm only

    def test_json_duplicate_takeoff_and_stop_during_command_sequence(self):
        fixture = self.project/'hil_bridge/commands/protocol_fixture.py'
        fixture.write_text("from commands.sequence import Wait\nON_FINISH='hold'\n"
                           "def build_sequence(): return [Wait(10)]\n")
        self.launch('protocol_fixture')
        self.wait(lambda: self.status_file().get('after_state') == 'running')
        status = self.run_command('status', '--json')
        self.assertEqual(status.returncode, 0, status.stdout+status.stderr)
        data = json.loads(status.stdout)  # no Python selection banner in stdout
        self.assertEqual(data['after_state'], 'running')
        duplicate = self.run_command('takeoff')
        self.assertEqual(duplicate.returncode, 2)
        self.assertIn('another takeoff/status is running', duplicate.stderr)
        stopped = self.run_command('stop-takeoff')
        self.assertEqual(stopped.returncode, 0, stopped.stdout+stopped.stderr)
        output = self.process.communicate(timeout=5)[0]
        self.assertEqual(self.process.returncode, 0, output)
        self.assertEqual(self.status_file()['after_state'], 'cancelled')
        self.assertFalse(self.status_file()['script_has_sticks'])

    def test_invalid_after_script_fails_before_sending_commands(self):
        invalid = self.run_command('takeoff', '--after', 'missing_script')
        self.assertEqual(invalid.returncode, 2)
        self.assertIn('command script not found', invalid.stderr)
        self.assertEqual(self.fc.commands, [])
        self.assertEqual(self.fc.manual, [])


if __name__ == '__main__':
    unittest.main()

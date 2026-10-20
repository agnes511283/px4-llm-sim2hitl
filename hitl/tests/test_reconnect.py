"""USB boot/application gating and native-Core recovery using no real devices."""
import json,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
RUNTIME=Path(__file__).resolve().parents[1];sys.path.insert(0,str(RUNTIME))
from platform_support import needs_model
from host.transport import SerialTransport,FakeFC
from host.serial_helpers import BOOTLOADER_LABEL
from host.core import Core
from pymavlink.dialects.v20 import common as mav

def wait(predicate,seconds=3):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if predicate():return
  time.sleep(.01)
 raise AssertionError('condition timeout')

class TransportTests(unittest.TestCase):
 def setUp(self):
  self.helpers=Mock();self.app=SimpleNamespace(path='/fake/usb',identity='usb:app',label='PX4 FMU v6C.x');self.boot=SimpleNamespace(path='/fake/usb',identity='usb:boot',label='PX4 BL FMU v6C.x')
  self.helpers.devices.return_value=[self.boot]
  self.helpers.choose_device.side_effect=lambda found,preferred,requested:next((x for x in found if preferred is None or x.identity==preferred.identity),None)
  with patch('host.transport.load_helpers',return_value=self.helpers):self.transport=SerialTransport(RUNTIME.parent,'/fake/usb')
  self.helpers.serial_owner.return_value=False
 def test_bootloader_never_opened_or_written(self):
  with patch('host.transport.serial.Serial') as opener:
   for _ in range(12):self.assertIs(self.transport.open(),False)
   opener.assert_not_called();self.assertEqual(self.transport.link_diagnostics()['state'],'bootloader')
 def test_ardupilot_bootloader_of_a_cube_never_opened(self):
  # CubePilot boards ship with the ArduPilot bootloader: "CubeOrange+-BL", same USB VID/PID as the PX4 firmware.
  self.boot.label='CubeOrange+-BL'
  with patch('host.transport.serial.Serial') as opener:
   for _ in range(3):self.assertIs(self.transport.open(),False)
   opener.assert_not_called();self.assertEqual(self.transport.link_diagnostics()['state'],'bootloader')
  for label in ['CubeOrange+','PX4 FMU v6C.x','Pixhawk-BLUE']:self.assertIsNone(BOOTLOADER_LABEL.search(label))
 def test_application_opens_after_bootloader_without_pinning_boot_identity(self):
  with patch('host.transport.serial.Serial') as opener:
   self.assertFalse(self.transport.open());self.assertIsNone(self.transport.preferred)
   self.helpers.devices.return_value=[self.app];self.assertTrue(self.transport.open());opener.assert_called_once();self.assertIs(self.transport.preferred,self.app)
 def test_bootloader_with_changed_pid_observed_but_not_selected(self):
  self.transport.preferred=self.app;self.transport.path=self.app.path
  with patch('host.transport.serial.Serial') as opener:self.assertFalse(self.transport.open());opener.assert_not_called()
  self.assertEqual(self.transport.link_info['state'],'bootloader');self.assertIs(self.transport.preferred,self.app)
 def test_metadata_not_ready_stays_silent(self):
  self.helpers.devices.return_value=[SimpleNamespace(path='/fake/usb',identity='path:/fake/usb',label='/fake/usb')]
  with patch('host.transport.serial.Serial') as opener:self.assertFalse(self.transport.open());opener.assert_not_called()
  self.assertEqual(self.transport.link_info['state'],'enumerating')
 def test_wrong_application_identity_does_not_replace_preferred(self):
  self.transport.preferred=self.app;self.helpers.devices.return_value=[SimpleNamespace(path='/fake/usb',identity='usb:other',label='PX4 FMU')]
  with patch('host.transport.serial.Serial') as opener:self.assertFalse(self.transport.open());opener.assert_not_called()
 def test_link_history_is_bounded(self):
  for k in range(100):self.helpers.devices.return_value=[self.app] if k%2 else [self.boot];self.transport.inspect_link(force=True)
  self.assertEqual(len(self.transport.link_events),64)

class SlowUSB(FakeFC):
 """Real-transport semantics with memory MAVLink only, no serial descriptor."""
 fake=False
 def __init__(self,delay=.3):
  super().__init__(RUNTIME.parent);self.delay=delay;self.boot_until=0;self.forever=False;self.writes_in_boot=[];self.closed_in_boot=0;self.events=[];self.reject_reboot=False;self.inspect_parser=mav.MAVLink(None)
 def phase(self):return 'bootloader' if self.forever or time.monotonic()<self.boot_until else 'application'
 def open(self):
  if self.phase()=='bootloader':return False
  super().open();return True
 def inspect_link(self,force=False):return self.phase()
 def link_diagnostics(self):return {'state':self.phase(),'events':self.events}
 def write(self,data):
  if self.phase()=='bootloader':self.writes_in_boot.append(bytes(data))
  before=len(self.command_ids);reject=self.reject_reboot and any(m.get_type()=='COMMAND_LONG' and m.command==246 for m in (self.inspect_parser.parse_buffer(data) or []));behavior=self.behavior
  if reject:self.behavior='reject'
  try:super().write(data)
  finally:self.behavior=behavior
  if not reject and len(self.command_ids)>before and self.command_ids[-1]==246:self.boot_until=time.monotonic()+self.delay;self.reboot_until=self.boot_until;self.events.append({'state':'bootloader','at':time.monotonic()})
 def close(self):
  if self.phase()=='bootloader':self.closed_in_boot+=1
  super().close()

@needs_model
class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.state=Path(self.temp.name)/'state';self.fc=SlowUSB();self.core=None
  self.state_patch=patch('host.ipc.state_path',return_value=self.state);self.state_patch.start()
 def tearDown(self):
  if self.core:self.core.close(force=True)
  self.state_patch.stop();self.temp.cleanup()
 def start(self):
  self.core=Core(RUNTIME,self.fc,Path(self.temp.name)/'logs',network=False);wait(lambda:self.core.status()['ready_to_start_model'],10)
 def test_cold_start_boot_delay_does_not_open_or_send(self):
  self.fc.boot_until=time.monotonic()+6.;self.fc.reboot_until=self.fc.boot_until;self.start();self.assertEqual(self.fc.writes_in_boot,[]);self.assertTrue(self.core.status()['ready_to_start_model'])
 def test_reboot_quiet_window_and_fresh_confirmation(self):
  self.start();self.core.recover();self.assertEqual(self.fc.writes_in_boot,[]);self.assertGreater(self.fc.closed_in_boot,0);self.assertTrue(self.core.status()['ready_after_recovery']);self.assertEqual(self.fc.command_ids,[400,246]);self.assertFalse(json.loads(self.core.recovery_file.read_text())['pending'])
 def test_boot_longer_than_old_five_second_probe_waits_without_tx(self):
  self.fc.delay=6.;self.start();start=time.monotonic();self.core.recover();self.assertGreaterEqual(time.monotonic()-start,6);self.assertEqual(self.fc.writes_in_boot,[]);self.assertTrue(self.core.status()['ready_after_recovery'])
 def test_failed_reboot_persists_pending_before_any_sensor_run(self):
  self.start();self.fc.delay=10.
  with patch('host.core.RECONNECT_TIMEOUT_S',.2):
   with self.assertRaisesRegex(RuntimeError,'Reconnection heartbeat timeout'):self.core.recover()
  self.assertTrue(json.loads(self.core.recovery_file.read_text())['pending']);self.assertTrue(self.core.recovery_required);self.assertEqual(self.core.worker.snapshot().produced,0);self.assertEqual(self.fc.writes_in_boot,[])
 def test_negative_reboot_ack_never_enters_success(self):
  self.start();self.fc.reject_reboot=True;self.fc.config['reject_result']=2
  with self.assertRaisesRegex(RuntimeError,'rejected'):self.core.recover()
  self.assertTrue(json.loads(self.core.recovery_file.read_text())['pending']);self.assertFalse(self.core.status()['ready_after_recovery'])

if __name__=='__main__':unittest.main(verbosity=2)

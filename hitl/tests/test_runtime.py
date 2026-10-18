import copy,ctypes as C,importlib.util,json,math,os,socket,sys,tempfile,time,unittest
from pathlib import Path
RUNTIME=Path(__file__).resolve().parents[1];sys.path.insert(0,str(RUNTIME))
from platform_support import needs_model
from host.core import Core
from host.transport import FakeFC
from host.ipc import Endpoint,request
from host.scenario import load_scene
from host.release import read_release
from host.abi import Model,Worker,Input,header
def wait(predicate,seconds=3):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if predicate():return
  time.sleep(.01)
 raise AssertionError('condition timeout')
@needs_model
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.fc=FakeFC(RUNTIME.parent);self.core=Core(RUNTIME,self.fc,self.tmp.name,network=False,fake_state_dir=Path(self.tmp.name)/'state');wait(lambda:self.core.status()['ready_to_start_model'])
 def tearDown(self):self.core.close(force=True);self.tmp.cleanup()
 def test_start_stop_reset_requires_recovery(self):
  self.core.start();wait(lambda:self.fc.counts.get('HIL_SENSOR',0)>10)
  with self.assertRaises(RuntimeError):self.core.start()
  self.core.stop();count=self.fc.counts['HIL_SENSOR'];time.sleep(.05);self.assertEqual(count,self.fc.counts['HIL_SENSOR'])
  with self.assertRaises(RuntimeError):self.core.reset()
  self.assertEqual(self.fc.command_ids,[])
 def test_recover_success_and_next_epoch(self):
  self.core.start();wait(lambda:self.fc.counts.get('HIL_SENSOR',0)>10);old=self.core.run_id;epoch=self.core.model_epoch_us;self.core.recover()
  self.assertTrue(self.core.status()['ready_after_recovery']);self.assertEqual(self.fc.command_ids,[400,246]);self.assertFalse(self.fc.armed)
  self.core.start();self.assertNotEqual(old,self.core.run_id);self.assertGreater(self.core.model_epoch_us,epoch)
 def test_recover_reject_stops_before_reboot(self):
  self.core.start();wait(lambda:self.fc.counts.get('HIL_SENSOR',0)>5);self.fc.behavior='reject'
  with self.assertRaises(RuntimeError):self.core.recover()
  self.assertEqual(self.core.recovery,'failed');self.assertEqual(self.fc.command_ids,[400]);self.assertTrue(self.core.recovery_required)
 def test_recovery_timeout_and_explicit_retry(self):
  self.fc.armed=True;self.fc.next_heartbeat=0;wait(lambda:self.core.fc['armed'] is True)
  self.fc.behavior='timeout';original=self.core._wait
  self.core._wait=lambda predicate,seconds,reason:original(predicate,min(seconds,.3),reason)
  with self.assertRaises(RuntimeError):self.core.recover()
  self.assertEqual(self.fc.command_ids,[400]);self.assertEqual(self.core.recovery,'failed')
  self.fc.behavior='success';self.core._wait=original;self.core.recover()
  self.assertEqual(self.fc.command_ids,[400,400,246]);self.assertTrue(self.core.status()['ready_after_recovery'])
 def test_unarmed_boundary(self):
  self.core.unarmed_only=True;self.core.start();self.fc.armed=True;self.fc.next_heartbeat=0;wait(lambda:self.core.state=='fault')
  self.assertEqual(self.fc.command_ids,[])
 def test_heartbeat_loss_keeps_unknown_and_fault(self):
  self.core.start();wait(lambda:self.fc.counts.get('HIL_SENSOR',0)>5);self.fc.behavior='lost';self.core.fc['heartbeat_at']=time.monotonic()-4;wait(lambda:self.core.state=='fault')
  self.assertNotEqual(self.core.fc['state'],'verified');self.assertTrue(self.core.recovery_required)
 def test_ipc_status_does_not_open_another_owner(self):
  endpoint=Endpoint(self.core)
  try:
   status=request(RUNTIME,'status',fake_state_dir=self.core.fake_state_dir);self.assertEqual(status['result']['instance_id'],self.core.instance_id)
   result=request(RUNTIME,'model-start',fake_state_dir=self.core.fake_state_dir);self.assertEqual(result['status'],'complete')
   result=request(RUNTIME,'model-stop',fake_state_dir=self.core.fake_state_dir);self.assertEqual(result['status'],'complete')
   result=request(RUNTIME,'model-reset',fake_state_dir=self.core.fake_state_dir);self.assertEqual(result['status'],'failed')
  finally:endpoint.close()
 def test_ipc_status_reply_larger_than_64_kib(self):
  # A status with many finished operations (e.g. parameter readbacks) outgrew the old 64 KiB reply read.
  import io
  from host.ipc import read_reply
  for n in range(32):self.core.operations.append({'request_id':f'old{n}','action':'param-readback','state':'complete','error':None,'result':{'note':'x'*1900,'more':'y'*1900}})
  endpoint=Endpoint(self.core)
  try:
   status=request(RUNTIME,'status',fake_state_dir=self.core.fake_state_dir)
   self.assertGreater(len(json.dumps(status)),65536);self.assertEqual(len(status['result']['operations']),32)
   self.assertEqual(request(RUNTIME,'model-start',fake_state_dir=self.core.fake_state_dir)['status'],'complete')
   self.assertEqual(request(RUNTIME,'model-stop',fake_state_dir=self.core.fake_state_dir)['status'],'complete')
  finally:endpoint.close()
  for raw in [b'',b'{"status": "comp']:  # closed early / cut off: a clear error, not a JSON parse of a fragment
   with self.assertRaisesRegex(ValueError,'reply incomplete'):read_reply(io.BytesIO(raw))
 def test_owner_refuses_too_many_waiting_or_unknown_requests(self):
  # Review 13 R13-5: at most MAX_UNFINISHED accepted or running operations; unknown actions and long request ids
  # are refused without an entry, so the status list stays bounded.
  import socket
  from host.ipc import remember,MAX_UNFINISHED,read_reply,state_path
  from host.errors import PreconditionError
  ops=[]
  for n in range(MAX_UNFINISHED):remember(ops,{'request_id':f'w{n}','state':'accepted'})
  with self.assertRaisesRegex(PreconditionError,'busy'):remember(ops,{'request_id':'one more','state':'accepted'})
  self.assertEqual(len(ops),MAX_UNFINISHED)
  endpoint=Endpoint(self.core)
  try:
   before=len(self.core.operations)
   reply=request(RUNTIME,'no-such-action',fake_state_dir=self.core.fake_state_dir)
   self.assertEqual(reply['status'],'failed');self.assertIn('Unknown operation',reply['error'])
   data=json.loads((state_path(RUNTIME,self.core.fake_state_dir)/'host.json').read_text())
   with socket.create_connection(('127.0.0.1',data['port']),timeout=3) as sock:
    sock.sendall((json.dumps({'token':data['token'],'instance_id':data['instance_id'],'request_id':'x'*65,
                              'action':'model-stop','arguments':{},'run_id':None})+'\n').encode())
    reply=read_reply(sock.makefile('rb'))
   self.assertEqual(reply['status'],'failed');self.assertIn('request_id',reply['error'])
   self.assertEqual(len(self.core.operations),before)
  finally:endpoint.close()
 def test_same_request_id_twice_at_once_runs_once(self):
  # Review 14 R14-3: two requests with one request_id arrive together (both pass the first lookup before either
  # is kept): the check and the keeping are one locked step, so the operation runs once and both get it.
  import threading
  from unittest.mock import patch
  import host.ipc as ipc
  from host.ipc import read_reply,state_path
  calls=[]
  self.core.read_parameters=lambda names:(calls.append(names),{'requested':names})[1]
  barrier=threading.Barrier(2,timeout=5);real=ipc.remember
  def together(operations,op):
   barrier.wait();return real(operations,op)
  endpoint=Endpoint(self.core);replies=[]
  try:
   data=json.loads((state_path(RUNTIME,self.core.fake_state_dir)/'host.json').read_text())
   def send():
    with socket.create_connection(('127.0.0.1',data['port']),timeout=5) as sock:
     sock.sendall((json.dumps({'token':data['token'],'instance_id':data['instance_id'],'request_id':'same-id',
                               'action':'read-parameters','arguments':{'names':[]},'run_id':self.core.run_id})+'\n').encode())
     replies.append(read_reply(sock.makefile('rb')))
   with patch.object(ipc,'remember',side_effect=together):
    threads=[threading.Thread(target=send) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join(10)
   wait(lambda:all(o['state'] in ['complete','failed'] for o in self.core.operations if o['request_id']=='same-id'))
   time.sleep(.2)
   self.assertEqual(len(replies),2);self.assertEqual(len(calls),1)
   self.assertEqual(sum(o['request_id']=='same-id' for o in self.core.operations),1)
  finally:endpoint.close()
  # Review 14 R14-2: the sent counts are always listed, 0 before anything was sent.
  metrics=self.core.status()['metrics'];self.assertEqual((metrics['tx_HIL_SENSOR'],metrics['tx_HIL_GPS']),(0,0))
 def test_waiting_client_gets_its_whole_result(self):
  # Review 12 N5: status lists summaries only; a waiting client takes its whole result by request_id, also
  # when more requests were accepted after its own; an unfinished operation is never dropped from the list.
  import threading
  from host.ipc import remember,KEEP_FINISHED
  def slow_list(out,log_id,list_only):
   time.sleep(.6);return {'entries':[{'id':i,'size':i} for i in range(20000)],'newest_id':19999,'complete':True}
  self.core.fetch_log=slow_list
  endpoint=Endpoint(self.core);replies={}
  try:
   waiting=threading.Thread(target=lambda:replies.update(log=request(RUNTIME,'fetch-log',{'list':True},fake_state_dir=self.core.fake_state_dir)))
   waiting.start();time.sleep(.2)
   later=[threading.Thread(target=lambda n=n:replies.update({n:request(RUNTIME,'read-parameters',{'names':[]},fake_state_dir=self.core.fake_state_dir)})) for n in range(6)]
   for t in later:t.start()
   waiting.join(20)
   for t in later:t.join(20)
   op=replies['log']['operation'];self.assertEqual(replies['log']['status'],'complete')
   self.assertEqual(len(op['result']['entries']),20000);self.assertNotIn('result_summarized',op)
   status=request(RUNTIME,'status',fake_state_dir=self.core.fake_state_dir)['result']
   self.assertTrue(status['operations_summarized']);self.assertLess(len(json.dumps(status)),300_000)
  finally:endpoint.close()
  ops=[{'request_id':'running','state':'running'}]
  for n in range(KEEP_FINISHED+8):remember(ops,{'request_id':f'f{n}','state':'complete'})
  self.assertEqual(len(ops),KEEP_FINISHED+1);self.assertEqual(ops[0]['request_id'],'running')
  self.assertEqual(ops[1]['request_id'],'f8')
 def test_duplicate_invalid_and_foreign_controls_do_not_refresh(self):
  from pymavlink.dialects.v20 import common as mav
  writer=mav.MAVLink(None,srcSystem=1,srcComponent=1)
  packet=mav.MAVLink_hil_actuator_controls_message(12345,[.1]*16,0,0).pack(writer)
  self.core._receive(packet,time.monotonic());age=self.core.control_at;sequence=self.core.control_sequence
  self.core._receive(packet,time.monotonic());self.assertEqual(sequence,self.core.control_sequence);self.assertEqual(age,self.core.control_at)
  packet=mav.MAVLink_hil_actuator_controls_message(12346,[float('nan')]*16,0,0).pack(writer)
  self.core._receive(packet,time.monotonic());self.assertEqual(sequence,self.core.control_sequence)
  other=mav.MAVLink(None,srcSystem=99,srcComponent=1)
  packet=mav.MAVLink_hil_actuator_controls_message(12347,[.2]*16,0,0).pack(other)
  self.core._receive(packet,time.monotonic());self.assertEqual(sequence,self.core.control_sequence)
class SceneTests(unittest.TestCase):
 def test_tas_body_conversion_and_exclusive_modes(self):
  s=json.loads((RUNTIME/'scenarios/ground.json').read_text());s.update(tas_m_s=20,alpha_deg=10,beta_deg=5);scene,i=load_scene(s)
  self.assertAlmostEqual(sum(v*v for v in i.body_velocity_m_s),400);self.assertGreater(i.body_velocity_m_s[1],0);self.assertGreater(i.body_velocity_m_s[2],0)
  s['body_velocity_m_s']=[0,0,0]
  with self.assertRaises(ValueError):load_scene(s)
 def test_unsupported_fields_are_rejected(self):
  base=json.loads((RUNTIME/'scenarios/ground.json').read_text())
  for name,value in [('site_msl_m',10),('geoid_separation_m',30),('seed_policy',1),('wind_ned_m_s',[1,0]),('wind',{'gust':{'length_m':[0,1,1]}}),('angular_rates_rad_s',[0,0,1]),('mass_kg',1.3),('height_agl_m',float('nan'))]:
   with self.subTest(name=name):
    s=dict(base);s[name]=value
    with self.assertRaises(ValueError):load_scene(s)
  s=dict(base);s['wind_ned_m_s']=[1,0,0];load_scene(s)  # a steady wind is a supported scene field now
 @needs_model
 def test_dependency_corruption_rejected(self):
  release,manifest=read_release(RUNTIME)
  with tempfile.TemporaryDirectory() as tmp:
   import shutil
   root=Path(tmp);shutil.copytree(release,root/'releases/test');(root/'active').mkdir();(root/'active'/(__import__('host.release',fromlist=['platform_id']).platform_id()+'.json')).write_text(json.dumps({'build_id':manifest['build_id'],'release':'releases/test','manifest_sha256':__import__('hashlib').sha256((root/'releases/test/manifest.json').read_bytes()).hexdigest()}));read_release(root);(root/'releases/test/profile.json').write_text('corrupt')
   with self.assertRaises(ValueError):read_release(root)
 @needs_model
 def test_native_snapshot_does_not_lose_short_new_flag(self):
  release,manifest=read_release(RUNTIME);m=Model(release/manifest['library']);m.reset();worker=Worker(release/manifest['worker'],m);worker.start()
  try:
   i=header(Input);i.actuator_valid=1;i.actuator_new=1;i.input_sequence=1;i.controls[0]=.3;i.actuator_age_ns=worker.now();worker.lib.hil_worker_input(C.byref(i));i.actuator_new=0;worker.lib.hil_worker_input(C.byref(i));time.sleep(.08)
   s=worker.snapshot();self.assertGreater(abs(s.output.raw_source[1]),.1)
  finally:worker.stop();m.lib.hil_model_terminate()
if __name__=='__main__':unittest.main(verbosity=2)

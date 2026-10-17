"""Public root entry -> IPC -> Core -> managed pilot -> routes -> FakeFC.

Synthetic FC telemetry is an orchestration fixture, independent of the source
plant. This suite opens no hardware serial port. Every host and client uses
--fake-fc, an isolated state directory, and four random localhost route ports.
Set FW_HIL_TEST_OUTPUT to retain the per-case wire/status/console evidence.
"""
import hashlib
import json
import struct
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pymavlink.dialects.v20 import common as mav
from platform_support import needs_model

PROJECT=Path(__file__).resolve().parents[2]
ENTRY=PROJECT/'runbridge'

@needs_model
class RunbridgeFakeTests(unittest.TestCase):
    def setUp(self):
        self.temp=None
        if os.environ.get('FW_HIL_TEST_OUTPUT'):
            self.folder=Path(os.environ['FW_HIL_TEST_OUTPUT'])/self._testMethodName
            self.folder.mkdir(parents=True,exist_ok=False)
        else:
            self.temp=tempfile.TemporaryDirectory(prefix='runbridge fake 專案 ');self.folder=Path(self.temp.name)
        ports=[]
        sockets=[]
        for _ in range(4):
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('127.0.0.1',0));sockets.append(s);ports.append(s.getsockname()[1])
        for s in sockets:s.close()
        self.routes={'qgc':ports[:2],'agent':ports[2:]}
        self.state=self.folder/'state';self.config_path=self.folder/'fake.json'
        self.config={'synthetic_flight':True,'routes':self.routes,'event_log':str(self.folder/'fc_events.jsonl')}
        self.write_config()
        self.common=['--fake-fc','--fake-state-dir',str(self.state)]
        self.env={**os.environ,'SKYSURFER_PYTHON':sys.executable,'PYTHONDONTWRITEBYTECODE':'1'}
        self.console=(self.folder/'host.log').open('w')
        self.host=subprocess.Popen([str(ENTRY),'bridge',*self.common,'--fake-config',str(self.config_path),'--log-dir',str(self.folder/'logs'),'--duration','90'],cwd=self.folder,env=self.env,stdout=self.console,stderr=subprocess.STDOUT)
        self.wait(lambda:self.status().get('ready_to_start_model'),8)
    def tearDown(self):
        try:
            if self.host.poll() is None:self.cli('shutdown','--force-exit',expected=0)
            self.host.wait(timeout=10)
        finally:
            if self.host.poll() is None:self.host.kill();self.host.wait(timeout=3)
            self.console.close()
            if self.temp:self.temp.cleanup()
    def write_config(self):
        temp=self.config_path.with_suffix('.tmp');temp.write_text(json.dumps(self.config));os.replace(temp,self.config_path)
    def cli(self,action,*args,expected=0):
        result=subprocess.run([str(ENTRY),action,*self.common,*args],cwd=self.folder,env=self.env,capture_output=True,text=True,timeout=45)
        with (self.folder/'cli.jsonl').open('a') as stream:stream.write(json.dumps({'action':action,'args':args,'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr})+'\n')
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return json.loads(result.stdout) if result.stdout else {}
    def status(self):
        try:
            result=subprocess.run([str(ENTRY),'status',*self.common,'--json'],cwd=self.folder,env=self.env,capture_output=True,text=True,timeout=5)
            return json.loads(result.stdout) if result.returncode==0 else {}
        except (ValueError,subprocess.TimeoutExpired):return {}
    def wait(self,predicate,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if predicate():return
            if self.host.poll() is not None:self.fail('host ended: '+(self.folder/'host.log').read_text())
            time.sleep(.05)
        self.fail('timeout: '+json.dumps(self.status()))
    def events(self):
        file=self.folder/'fc_events.jsonl'
        return [json.loads(s) for s in file.read_text().splitlines()] if file.exists() else []
    def command_ids(self):return [e['message']['command'] for e in self.events() if e['message']['mavpackettype']=='COMMAND_LONG']
    def send(self,role,*messages):
        writer=mav.MAVLink(None,srcSystem=255 if role=='qgc' else 254,srcComponent=190)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:sock.sendto(b''.join(m.pack(writer) for m in messages),('127.0.0.1',self.routes[role][0]))
    def test_takeoff_stop_recover_next_run_and_after(self):
        self.assertFalse(self.status()['control_gate']['enabled'])
        self.cli('model-start');run=self.status()['run_id']
        result=self.cli('takeoff','--record')
        self.assertEqual(result['operation']['result']['milestone'],'pilot_started')
        self.assertFalse(result['operation']['result']['flight_complete'])
        self.wait(lambda:self.status().get('pilot',{}).get('state')=='cruise')
        self.assertIn(176,self.command_ids());self.assertIn(400,self.command_ids())
        self.cli('takeoff',expected=2)
        self.cli('stop-takeoff');self.assertFalse(self.status()['pilot']['running'])
        self.assertEqual(self.status()['model'],'running')
        self.cli('model-stop');before=self.status();self.assertTrue(before['recovery_required'])
        self.cli('model-reset',expected=2)
        self.cli('recover');s=self.status();self.assertTrue(s['ready_after_recovery']);self.assertFalse(s['fc']['armed'])
        self.assertTrue(all(e['message'].get('param2',0)==0 for e in self.events() if e['message']['mavpackettype']=='COMMAND_LONG' and e['message']['command']==400 and e['message']['param1']==0))
        self.cli('model-start');self.assertNotEqual(run,self.status()['run_id'])
        self.cli('takeoff','--after','after_takeoff_template','--after-stable-seconds','1')
        self.wait(lambda:self.status().get('pilot',{}).get('after_state')=='complete')
        self.assertTrue(list((self.folder/'logs/pilot').glob('*_wire.bin')))
        self.cli('recover');self.assertTrue(self.status()['ready_after_recovery'])
    def test_invalid_script_and_settings_fail_before_flight_commands(self):
        self.cli('model-start')
        self.cli('takeoff','--after','review_missing_script',expected=2)
        self.cli('takeoff','--takeoff-throttle','2',expected=2)
        self.assertEqual(self.command_ids(),[]);self.assertFalse(self.status()['pilot']['running'])
    def test_agent_port_collision_is_reported_as_failure(self):
        self.cli('model-start')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as occupied:
            occupied.bind(('127.0.0.1',self.routes['agent'][1]))
            result=self.cli('takeoff',expected=3)
            self.assertIn('startup failed',result['operation']['error'])
        self.assertEqual(self.command_ids(),[]);self.assertEqual(self.status()['pilot']['phase'],'failed')
    def test_qgc_handover_uses_new_runtime_route(self):
        self.cli('model-start');self.cli('takeoff')
        self.wait(lambda:self.status().get('pilot',{}).get('state')=='cruise')
        for value in [100,100,100,500,500,500]:
            self.send('qgc',mav.MAVLink_manual_control_message(1,0,0,value,0,0));time.sleep(.08)
        self.wait(lambda:not self.status().get('pilot',{}).get('running'))
        self.assertIn('pilot has control',self.status()['pilot']['reason'])
        time.sleep(.25);self.send('qgc',mav.MAVLink_manual_control_message(1,0,0,432,0,0))
        self.wait(lambda:any(e['system']==255 and e['message']['mavpackettype']=='MANUAL_CONTROL' and e['message']['z']==432 for e in self.events()))
    def test_recover_rejection_with_heartbeat_never_reboots_and_retry(self):
        self.cli('model-start');self.config['behavior']='reject_with_heartbeat';self.write_config();time.sleep(.1)
        result=self.cli('recover',expected=3);self.assertIn('rejected',result['operation']['error'])
        self.assertEqual(self.command_ids(),[400]);self.assertTrue(self.status()['recovery_required'])
        self.config['behavior']='success';self.write_config();time.sleep(.1)
        self.cli('recover');self.assertTrue(self.status()['ready_after_recovery'])
    def test_recover_timeout_does_not_reboot(self):
        self.cli('model-start');self.config['behavior']='timeout';self.write_config();time.sleep(.1)
        result=self.cli('recover',expected=3);self.assertIn('timeout',result['operation']['error'])
        self.assertEqual(self.command_ids(),[400]);self.assertFalse(self.status()['control_gate']['enabled'])
    def test_recovery_completes_with_forwarded_qgc_traffic(self):
        # Everything is forwarded during recover too (BEHAVIOR_CONTRACT 5); parameter reads and writes
        # do not disturb it. An arm or mode command sent during recover would reach the FC and can make
        # recover fail; that is documented, not tested.
        self.cli('model-start')
        with (self.folder/'recover.log').open('w') as console:
            process=subprocess.Popen([str(ENTRY),'recover',*self.common],cwd=self.folder,env=self.env,stdout=console,stderr=subprocess.STDOUT)
            try:
                self.wait(lambda:self.status().get('recovery') in ['rebooting','waiting_link'])
                for _ in range(5):
                    self.send('qgc',mav.MAVLink_param_request_read_message(1,1,b'SYS_HITL',-1),mav.MAVLink_param_set_message(1,1,b'SDLOG_PROFILE',17,6))
                    time.sleep(.02)
                self.assertEqual(process.wait(timeout=15),0,(self.folder/'recover.log').read_text())
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=3)
        self.assertEqual(self.command_ids(),[400,246]);self.assertTrue(self.status()['ready_after_recovery'])
        self.assertEqual(self.status()['metrics'].get('blocked_external_control',0),0)
        self.assertTrue(any(e['system']==255 and e['message']['mavpackettype']=='PARAM_SET' for e in self.events()))
    def test_late_pilot_exit_is_visible_as_failed(self):
        self.config['telemetry_enabled']=False;self.write_config();time.sleep(.15)
        self.cli('model-start');self.cli('takeoff')
        self.wait(lambda:self.status().get('pilot',{}).get('phase')=='failed',20)
        s=self.status();self.assertEqual(s['pilot']['exit_code'],2)
        self.assertIn('no telemetry',s['pilot']['reason']);self.assertIn('Pilot exited 2',s['last_error'])
        self.assertEqual(self.command_ids(),[])
    def test_controls_loss_while_pilot_active_blocks_remaining_sticks(self):
        self.cli('model-start');self.cli('takeoff')
        self.wait(lambda:self.status().get('pilot',{}).get('state')=='cruise')
        self.config['controls_enabled']=False;self.write_config()
        self.wait(lambda:self.status().get('model')=='fault',6)
        # Every automatic MANUAL_CONTROL after the confirmed fault is blocked.
        cutoff=time.monotonic();time.sleep(.4)
        self.assertFalse(any(e['time']>cutoff and e['message']['mavpackettype']=='MANUAL_CONTROL' for e in self.events()))
        self.wait(lambda:not self.status()['pilot']['running'])
        self.assertFalse(self.status()['control_gate']['enabled'])
    def test_force_shutdown_with_frozen_pilot_preserves_failure(self):
        self.cli('model-start');self.cli('takeoff');os.kill(self.status()['pilot']['pid'],signal.SIGSTOP)
        self.cli('shutdown','--force-exit');self.host.wait(timeout=10)
        s=json.loads((self.folder/'logs/final_status.json').read_text())
        self.assertEqual(s['recovery'],'failed');self.assertTrue(s['recovery_required'])
        self.assertEqual(s['model'],'fault');self.assertFalse(s['pilot']['running'])
        self.assertEqual(s['metrics']['shutdown_stop_failures'],1)
    def test_fetch_log_downloads_newest_and_refills_gaps(self):
        sys.path.insert(0,str(PROJECT/'hitl'))
        from host.transport import FakeFC
        import hashlib
        expected=FakeFC().fake_logs()
        # Every 7th LOG_DATA piece is lost, and heartbeats pause 4 s (> the 3 s stale limit) on the first request.
        self.config.update(log_drop_every=7,log_heartbeat_gap_s=4,fc_logs=[4000,400003]);self.write_config();time.sleep(.15)
        expected=FakeFC(config_path=self.config_path).fake_logs()
        result=self.cli('fetch-log','--out',str(self.folder/'fc'))['operation']['result']
        self.assertEqual((result['id'],result['size'],result['logs_on_fc']),(2,len(expected[1]),2))
        self.assertEqual(Path(result['path']).read_bytes(),expected[1])
        self.assertEqual(result['sha256'],hashlib.sha256(expected[1]).hexdigest())
        self.assertGreater(result['requests'],1)  # the gaps were re-requested
        older=self.cli('fetch-log','--out',str(self.folder/'fc'),'--log-id','1')['operation']['result']
        self.assertEqual(Path(older['path']).read_bytes(),expected[0])
        self.cli('fetch-log','--out',str(self.folder/'fc'),'--log-id','9',expected=3)
        self.assertGreater(result['seconds'],3)  # the download outlasted the 4 s heartbeat pause (FC stale)
        self.wait(lambda:self.status().get('ready_to_start_model'))
        self.cli('model-start');self.cli('fetch-log','--out',str(self.folder/'fc'),expected=2)  # never while running
        self.cli('fetch-log',expected=4)  # --out is required
        self.cli('model-stop');self.cli('recover')
        listed=self.cli('fetch-log','--list')['operation']['result']
        self.assertEqual((listed['newest_id'],listed['complete'],len(listed['entries'])),(2,True,2))
        # An incomplete piece is not accepted (re-requested); an incomplete list refuses 'newest'.
        self.config.update(log_short_piece=True,log_heartbeat_gap_s=0);self.write_config();time.sleep(.15)
        short=self.cli('fetch-log','--out',str(self.folder/'fc2'))['operation']['result']
        self.assertEqual(Path(short['path']).read_bytes(),expected[1]);self.assertEqual(short['short_pieces_rejected'],1)
        self.config.update(log_list_drop_newest=True);self.write_config();time.sleep(.15)
        failed=self.cli('fetch-log','--out',str(self.folder/'fc3'),expected=3)
        self.assertIn('incomplete',failed['operation']['error'])
    def test_fetch_log_goes_on_after_pauses_without_resending(self):
        # As FC log 37 on 2026-10-16: PX4 pauses in the middle of a range (~2 s) and a piece goes missing now and
        # then. The download waits out a pause and goes on where the stream stopped; the lost pieces are asked
        # for at the end, so almost nothing is sent twice (with the old 0.5 s re-request from the first gap,
        # 53 % of the pieces were duplicates).
        sys.path.insert(0,str(PROJECT/'hitl'))
        from host.transport import FakeFC
        self.config.update(log_pause_s=2,log_drop_every=500,fc_logs=[4000,2_000_000]);self.write_config();time.sleep(.15)
        expected=FakeFC(config_path=self.config_path).fake_logs()[1]
        result=self.cli('fetch-log','--out',str(self.folder/'fc'))['operation']['result']
        self.assertEqual(Path(result['path']).read_bytes(),expected)
        asked=sum(e['message']['count'] for e in self.events() if e['message']['mavpackettype']=='LOG_REQUEST_DATA')
        self.assertLess(asked,1.05*len(expected),result)
    def test_param_readback_reads_used_and_unused_parameters(self):
        # Every 9th list item is lost in the stream (re-requested by index); unused parameters come by name.
        self.config.update(param_list_drop_every=9);self.write_config();time.sleep(.15)
        result=self.cli('param-readback','--out',str(self.folder/'params'))['operation']['result']
        self.assertEqual(result['verdict'],'PASS');self.assertEqual(result['total_received'],2038)
        self.assertEqual(result['used_received'],result['param_count_used'])
        self.assertEqual(result['used_received']+result['by_name_received'],2038)
        self.assertGreater(result['requests'],1+result['by_name_received'])  # the lost indices were re-requested
        data=json.loads(Path(result['path']).read_text());values={p['name']:p for p in data['parameters']}
        self.assertEqual((values['SYS_HITL']['value'],values['SYS_AUTOSTART']['value']),(1,2100))
        self.assertEqual((values['FW_MAN_P_MAX']['type'],values['FW_MAN_P_MAX']['value']),(9,30.0))
        self.assertEqual(data['autopilot_version']['git_hash_prefix'],'d6f12ad1c4')
        rows=[l.split('\t') for l in Path(result['params_file']).read_text().splitlines() if not l.startswith('#')]
        self.assertEqual(len(rows),2038);self.assertIn(['1','1','SYS_AUTOSTART','2100','6'],rows)
        self.cli('model-start');self.cli('param-readback','--out',str(self.folder/'p2'),expected=2)  # never while running
        self.cli('param-readback',expected=4)  # --out is required
        self.cli('model-stop');self.cli('recover')
        # A listed name the FC does not answer, a parameter outside the firmware list (lost in the list stream, so
        # only its index can fetch it), a parameter of another type: INCOMPLETE (exit 5).
        self.config.update(param_list_drop_every=0,param_unknown=['PWM_AUX_FUNC1'],param_extra={'ZZ_TEST':3},
                           param_wrong_type=['FW_R_TC'],param_list_drop=['ZZ_TEST'])
        self.write_config();time.sleep(.15)
        bad=self.cli('param-readback','--out',str(self.folder/'p3'),expected=5)['operation']['result']
        self.assertEqual(bad['verdict'],'INCOMPLETE')
        self.assertEqual((bad['missing'],bad['not_in_list'],bad['type_mismatch']),(['PWM_AUX_FUNC1'],['ZZ_TEST'],['FW_R_TC']))
        self.assertTrue(Path(bad['path']).exists())
    def test_param_plan_and_deploy_cli(self):
        self.config.update(param_initial={'HIL_ACT_REV':0});self.write_config();time.sleep(.15)
        plan=self.cli('param-plan','--out',str(self.folder/'plan'))['operation']['result']
        self.assertEqual([(w['name'],w['old'],w['new']) for w in plan['writes']],[('HIL_ACT_REV',0,2)])
        self.cli('param-deploy',expected=4)  # --out is required
        # The FC never applies it: FAIL (exit 3); the value was never changed, so nothing had to be restored.
        self.config.update(param_set_ignore={'HIL_ACT_REV':['02000000']});self.write_config();time.sleep(.15)
        failed=self.cli('param-deploy','--out',str(self.folder/'d1'),expected=3)['operation']['result']
        self.assertEqual((failed['verdict'],failed['restored']),('FAIL',[]))
        self.assertEqual(json.loads(Path(failed['journal']).read_text())['entries'][0]['rollback'],'unchanged')
        self.config.pop('param_set_ignore');self.write_config();time.sleep(.15)
        done=self.cli('param-deploy','--out',str(self.folder/'d2'))['operation']['result']
        self.assertEqual((done['verdict'],done['written']),('PASS',['HIL_ACT_REV']))
        again=self.cli('param-plan','--out',str(self.folder/'plan2'))['operation']['result']
        self.assertEqual(again['writes'],[])
    def test_sd_card_cli(self):
        extras='/fs/microsd/etc/extras.txt';local=self.folder/'extras.txt';local.write_bytes(b'sks_hello start\n')
        self.assertEqual(self.cli('sd-list','--sd-path','/fs/microsd')['operation']['result']['entries'],[{'type':'dir','name':'log'}])
        self.cli('sd-put','--sd-path',extras,'--out',str(self.folder/'p'),expected=4)  # --file is required
        self.cli('sd-put','--file',str(local),'--sd-path','/fs/microsd/etc/rc.txt','--out',str(self.folder/'p'),expected=4)
        put=self.cli('sd-put','--file',str(local),'--sd-path',extras,'--out',str(self.folder/'p'))['operation']['result']
        self.assertEqual((put['verdict'],put['changed']),('PASS',True))
        self.assertIn(246,self.command_ids())  # rebooted, then read back
        got=self.cli('sd-get','--sd-path',extras,'--out',str(self.folder/'g'))['operation']['result']
        self.assertEqual(Path(got['file']).read_bytes(),b'sks_hello start\n')
        gone=self.cli('sd-rm','--sd-path',extras,'--out',str(self.folder/'r'))['operation']['result']
        self.assertEqual((gone['verdict'],gone['changed']),('PASS',True))
        self.assertEqual(self.cli('sd-list')['operation']['result']['entries'],[])
    def test_fault_stops_sensor_and_still_forwards_external(self):
        self.cli('model-start');self.config['controls_enabled']=False;self.write_config()
        self.wait(lambda:self.status().get('model')=='fault',6)
        self.send('agent',mav.MAVLink_command_long_message(1,1,400,0,1,0,0,0,0,0,0),mav.MAVLink_manual_control_message(1,0,0,500,0,0))
        time.sleep(.2);self.assertEqual(self.command_ids(),[400])  # forwarded: HIL drives no hardware
        self.assertEqual(self.status()['metrics'].get('blocked_external_control',0),0)
        count=self.status()['metrics'].get('tx_HIL_SENSOR',0);time.sleep(.1)
        self.assertEqual(count,self.status()['metrics'].get('tx_HIL_SENSOR',0))
    def test_frozen_pilot_is_reaped_and_model_stopped(self):
        self.cli('model-start');self.cli('takeoff')
        s=self.status();pid=s['pilot']['pid'];os.kill(pid,signal.SIGSTOP)
        result=self.cli('model-stop',expected=3);self.assertIn('stop timed out',result['operation']['error'])
        s=self.status();self.assertEqual(s['model'],'fault');self.assertFalse(s['pilot']['running'])
        self.assertFalse(s['control_gate']['enabled']);self.assertTrue(s['recovery_required'])
    def test_second_host_refused_and_real_state_override_rejected(self):
        result=subprocess.run([str(ENTRY),'bridge',*self.common],cwd=self.folder,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertIn('Host already running',result.stderr)
        result=subprocess.run([str(ENTRY),'bridge','--fake-state-dir',str(self.state)],cwd=self.folder,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,4);self.assertIn('requires --fake-fc',result.stderr)

    def test_root_takeoff_hold_workflow_and_force_recovery(self):
        self.config['reject_normal_disarm']=True;self.write_config();time.sleep(.1)
        result=self.cli('test-takeoff-hold','--log-dir',str(self.folder/'workflow'),'--hold-seconds','1','--hold-timeout','25','--flight-timeout','35')
        self.assertEqual(result['status'],'PASS')
        report=json.loads((self.folder/'workflow/result.json').read_text())
        self.assertGreaterEqual(report['orbit']['turns'],1.)
        self.assertTrue(report['after_recovery']['recovery_details']['force_disarm_used'])
        self.assertFalse(self.status()['recovery_required'])
        commands=[e['message'] for e in self.events() if e['message']['mavpackettype']=='COMMAND_LONG']
        self.assertTrue(any(m['command']==176 and m['param2']==4 and m['param3']==3 for m in commands))
        self.assertTrue(any(m['command']==400 and m['param1']==0 and m['param2']==21196 for m in commands))
        self.assertTrue(self.status()['ready_after_recovery'])
        # The newest FC log is downloaded after recovery into the test's log directory.
        self.assertEqual((report['fc_log_before'],report['fc_log']['id']),(2,3))  # the flight's arm made log 3
        self.assertNotIn('error',report['fc_log'])
        self.assertTrue(Path(report['fc_log']['path']).is_file())
        self.assertEqual(Path(report['fc_log']['path']).parent,(self.folder/'workflow/fc_log').resolve())
        # flight-summary works with this (shared) owner: its log directory and only this test's timing rows.
        summary=self.cli('flight-summary','--log-dir',str(self.folder/'workflow'),expected=3)
        self.assertEqual(summary['failures'],['hold shorter than 60 s'])  # the test used --hold-seconds 1
        self.assertEqual(Path(summary['host_log']).resolve(),(self.folder/'logs').resolve())
        self.assertGreater(summary['timing']['steps'],0)
        self.assertEqual(summary['ending_source'],'result.json after_recovery')

    def hitl_run(self,*args,expected,timeout=120,during_flight=None):
        """hitl-run (BEHAVIOR_CONTRACT 7e) into self.folder/'runs': (manifest, run directory). during_flight() is
        called once the flight has started (after the readback before it)."""
        process=subprocess.Popen([str(ENTRY),'hitl-run',*self.common,'--out',str(self.folder/'runs'),*args],cwd=self.folder,
                                 env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if during_flight:
            end=time.monotonic()+60
            while not list((self.folder/'runs').glob('run_*/flight/operations.jsonl')) and time.monotonic()<end:time.sleep(.1)
            during_flight()
        stdout,stderr=process.communicate(timeout=timeout)
        result=subprocess.CompletedProcess(process.args,process.returncode,stdout,stderr)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        line=json.loads(result.stdout.strip().splitlines()[-1])
        manifest=json.loads(Path(line['manifest']).read_text())
        self.assertEqual(manifest['verdict'],line['verdict'])
        run=Path(line['manifest']).parent
        for entry in manifest['files']:  # every file of the run is listed with its SHA-256
            self.assertEqual(hashlib.sha256((run/entry['path']).read_bytes()).hexdigest(),entry['sha256'],entry['path'])
        return manifest,run
    def test_hitl_run_judges_every_part(self):
        sys.path.insert(0,str(PROJECT/'hitl'))
        # The test's short Hold fails flight-summary (60 s minimum), and QGC changes a parameter during the flight
        # (forwarded to the FC): the flight and parameter parts are FAIL, every other part PASS.
        qgc=lambda:self.send('qgc',mav.MAVLink_param_set_message(1,1,b'FW_R_TC',0.9,9))
        manifest,run=self.hitl_run('--hold-seconds','1','--hold-timeout','25','--flight-timeout','35',expected=3,during_flight=qgc)
        verdicts={k:v['verdict'] for k,v in manifest['parts'].items()}
        self.assertEqual(verdicts,{'identity':'PASS','params_before':'PASS','flight':'FAIL','identity_end':'PASS',
                                   'params_after':'FAIL','fc_log':'PASS','data':'PASS'})
        # The FC log was downloaded twice (same bytes) and parses strictly (a corrupting firmware fails here).
        log=manifest['parts']['fc_log'];self.assertEqual(log['second_sha256'],log['sha256']);self.assertTrue(log['strict']['ok'])
        self.assertEqual(manifest['parts']['flight']['reasons'],['hold shorter than 60 s'])
        self.assertEqual(manifest['params']['after']['changed_other'],['FW_R_TC'])
        # Review 11 F5: this run's raw data is kept with the manifest and checked: every HIL_SENSOR of the run is
        # in the wire slice, the timing rows are the run's consecutive steps.
        data=manifest['parts']['data'];files={f['path'] for f in manifest['files']}
        self.assertIn('host/wire.bin',files);self.assertIn('host/timing.csv',files)
        expected=data['wire']['sensor_packets'];self.assertEqual(data['wire']['found'],expected)
        from host.hitl_run import wire_slice  # the kept slice itself holds all of them, all valid
        size=(run/'host/wire.bin').stat().st_size
        self.assertEqual(wire_slice(run/'host/wire.bin',0,size),((0,size),expected,0))
        self.assertEqual(data['wire']['bad_frames'],0)
        self.assertEqual(data['timing']['rows'],json.loads((run/'flight/result.json').read_text())['after_model_stop']['produced_steps'])
        self.assertEqual(manifest['runtime']['source_id_owner'],manifest['runtime']['source_id_disk'])
        self.assertEqual(manifest['firmware']['sha256'],hashlib.sha256((PROJECT/'deploy/00_native/firmware/px4_fmu-v6c_default.px4').read_bytes()).hexdigest())
        self.assertEqual(manifest['scenario']['flight'],{'altitude':100,'hold_seconds':1.0,'hold_timeout':25.0,'flight_timeout':35.0})
        self.assertTrue((run/'flight/result.json').is_file());self.assertTrue((run/'params_before').is_dir())
    def test_hitl_run_refuses_wrong_parameters_before_flying(self):
        self.config['param_initial']={'HIL_ACT_REV':0};self.write_config();time.sleep(.15)
        manifest,run=self.hitl_run(expected=2)
        self.assertEqual(manifest['verdict'],'NOT_RUN');self.assertEqual(manifest['parts']['params_before']['verdict'],'FAIL')
        self.assertNotIn('flight',manifest['parts']);self.assertFalse((run/'flight').exists())
        self.assertNotIn(176,self.command_ids())  # no mode change, no takeoff
        self.assertNotIn('PARAM_SET',[e['message']['mavpackettype'] for e in self.events()])  # nothing written
    def test_hitl_run_flight_pass_does_not_hide_missing_evidence(self):
        # A full 60 s Hold passes flight-summary, but this flight's FC log cannot be listed: INCOMPLETE, not PASS.
        self.cli('shutdown','--force-exit');self.host.wait(timeout=10)
        self.host=subprocess.Popen([str(ENTRY),'bridge',*self.common,'--fake-config',str(self.config_path),'--log-dir',
                                    str(self.folder/'logs2'),'--duration','240'],cwd=self.folder,env=self.env,stdout=self.console,stderr=subprocess.STDOUT)
        self.wait(lambda:self.status().get('ready_to_start_model'),8)
        self.config['log_list_drop_newest']=True;self.write_config();time.sleep(.15)
        manifest,run=self.hitl_run(expected=5,timeout=220)
        verdicts={k:v['verdict'] for k,v in manifest['parts'].items()}
        self.assertEqual(verdicts['flight'],'PASS',manifest['parts']['flight']);self.assertEqual(verdicts['fc_log'],'INCOMPLETE')
        self.assertEqual(manifest['verdict'],'INCOMPLETE')

    def test_fake_flag_never_reaches_another_owner(self):
        # Review 11 F4: --fake-fc without its own state directory would talk to the real owner (and skip the flight
        # dialogs): refused. And the owner says what it drives: a client that disagrees is refused before flying.
        # Review 12 N2: also a fake owner (bridge) needs its own state directory: the real one holds the real
        # owner's recovery marker and deploy latch.
        for argv in [['hitl-run','--fake-fc','--altitude','50'],['test-takeoff-hold','--fake-fc','--altitude','50'],
                     ['status','--fake-fc'],['bridge','--fake-fc']]:
            result=subprocess.run([str(ENTRY),*argv],cwd=self.folder,env=self.env,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,4,argv);self.assertIn('needs --fake-state-dir',result.stderr)
        # Attaching to a running owner compares what the owner drives, never the client's own flag.
        sys.path.insert(0,str(PROJECT/'hitl'))
        import main as entry
        from unittest.mock import patch as mock_patch
        with mock_patch.object(entry,'request',return_value={'status':'complete','result':{'fake_fc':False}}):
            with self.assertRaisesRegex(RuntimeError,'fake_fc=False'):
                entry.main(['bridge','--fake-fc','--fake-state-dir',str(self.state)])
        sys.path.insert(0,str(PROJECT/'hitl'))
        from types import SimpleNamespace
        from host.hitl_run import run_hitl
        from host.flight_test import run_test
        args=SimpleNamespace(fake_fc=False,fake_state_dir=self.state,fake_config=None,port='auto',release=None,
                             out=self.folder/'mismatch',altitude=None,hold_seconds=None,hold_timeout=None,flight_timeout=None)
        import contextlib,io
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run_hitl(PROJECT/'hitl',args),2)
        manifest=json.loads(next((self.folder/'mismatch').glob('run_*/manifest.json')).read_text())
        self.assertEqual(manifest['verdict'],'NOT_RUN');self.assertIn('fake_fc',' '.join(manifest['parts']['identity']['reasons']))
        flight=SimpleNamespace(fake_fc=False,fake_state_dir=self.state,fake_config=None,port='auto',log_dir=self.folder/'mismatch_flight',
                               altitude=100.,hold_seconds=60.,hold_timeout=180.,flight_timeout=300.)
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run_test(PROJECT/'hitl',flight),3)
        report=json.loads((self.folder/'mismatch_flight/result.json').read_text())
        self.assertIn('owner fake_fc=True',report['error'])
        self.assertNotIn(176,self.command_ids())  # no mode change, no takeoff
    def test_hitl_run_keeps_a_manifest_when_a_check_breaks(self):
        # Review 11 F6: an unexpected failure after the flight (here an IPC timeout of the readback) still ends
        # with a manifest: that part INCOMPLETE, the others checked.
        sys.path.insert(0,str(PROJECT/'hitl'))
        from types import SimpleNamespace
        import contextlib,io
        import host.hitl_run as hr
        real=hr.request
        def timeout_after_flight(runtime,action,arguments=None,**kwargs):
            if action=='param-readback' and str((arguments or {}).get('out','')).endswith('params_after'):
                raise TimeoutError('timed out')
            return real(runtime,action,arguments,**kwargs)
        args=SimpleNamespace(fake_fc=True,fake_state_dir=self.state,fake_config=None,port='auto',release=None,
                             out=self.folder/'broken',altitude=None,hold_seconds=1.,hold_timeout=25.,flight_timeout=35.)
        from unittest.mock import patch
        with patch.object(hr,'request',side_effect=timeout_after_flight),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hr.run_hitl(PROJECT/'hitl',args),3)  # the 1 s Hold makes the flight FAIL
        manifest=json.loads(next((self.folder/'broken').glob('run_*/manifest.json')).read_text())
        part=manifest['parts']['params_after'];self.assertEqual(part['verdict'],'INCOMPLETE')
        self.assertIn('TimeoutError',part['reasons'][0])
        self.assertEqual({k:manifest['parts'][k]['verdict'] for k in ['identity_end','fc_log','data']},
                         {'identity_end':'PASS','fc_log':'PASS','data':'PASS'})

    def fixture_flight(self,report):
        """A run_test stand-in that only writes result.json (report) into the run's flight directory."""
        def run_test(runtime,args):
            Path(args.log_dir).mkdir(parents=True,exist_ok=True)
            (Path(args.log_dir)/'result.json').write_text(json.dumps(report));return 3
        return run_test
    def run_hitl_with(self,out,**patches):
        sys.path.insert(0,str(PROJECT/'hitl'))
        from types import SimpleNamespace
        import contextlib,io
        import host.hitl_run as hr,host.flight_test as ft
        from unittest.mock import patch as mock_patch
        args=SimpleNamespace(fake_fc=True,fake_state_dir=self.state,fake_config=None,port='auto',release=None,
                             out=self.folder/out,altitude=None,hold_seconds=1.,hold_timeout=25.,flight_timeout=35.)
        with contextlib.ExitStack() as stack:
            for name,value in patches.items():stack.enter_context(mock_patch.object(ft,name,value))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code=hr.run_hitl(PROJECT/'hitl',args)
        return code,json.loads(next((self.folder/out).glob('run_*/manifest.json')).read_text())
    def test_hitl_run_known_failure_stays_fail(self):
        # Review 12 N4: the flight test recorded FAIL; its timing evidence is missing (flight-summary cannot read
        # it): the flight part stays FAIL. The manifest checks the FC log id itself (not newer than before: not
        # provably this flight's log).
        log=self.folder/'old.ulg';log.write_bytes(b'ULog')
        report={'status':'FAIL','flight':'FAIL','recovery':'PASS','error':'known model fault','fc_log_before':2,
                'fc_log':{'id':2,'path':str(log),'sha256':hashlib.sha256(b'ULog').hexdigest(),'size':4}}
        code,manifest=self.run_hitl_with('known',run_test=self.fixture_flight(report))
        self.assertEqual((code,manifest['verdict']),(3,'FAIL'))
        flight=manifest['parts']['flight'];self.assertEqual(flight['verdict'],'FAIL')
        self.assertIn('known model fault',flight['reasons'][0]);self.assertIn('cannot be judged',' '.join(flight['reasons']))
        self.assertEqual(manifest['parts']['fc_log']['verdict'],'INCOMPLETE')
        self.assertIn('not newer',manifest['parts']['fc_log']['reasons'][0])
    def test_hitl_run_checks_after_a_flight_test_that_raised(self):
        # Review 12 N4: a flight test that raises leaves the flight part INCOMPLETE; the read-only checks after
        # it still run.
        def broken(runtime,args):raise RuntimeError('pilot crashed')
        code,manifest=self.run_hitl_with('raised',run_test=broken)
        self.assertEqual((code,manifest['verdict']),(5,'INCOMPLETE'))
        self.assertIn('pilot crashed',' '.join(manifest['parts']['flight']['reasons']))
        self.assertEqual(manifest['parts']['identity_end']['verdict'],'PASS')
        self.assertEqual(manifest['parts']['params_after']['verdict'],'PASS')

    def test_hitl_run_takes_only_this_runs_wire(self):
        # Review 13 R13-3: the native counters restart at every reconnection (each test starts with a reboot), so a
        # later run on one owner counts from 0 again: its records are those between the wire.bin sizes taken before
        # model-start and after model-stop. R13-6: no newest log before the flight is no baseline (INCOMPLETE).
        # R13-7: a file that cannot be read at the end is listed with its error; the manifest is still written.
        writer=mav.MAVLink(None,srcSystem=2,srcComponent=51)
        record=lambda data:struct.pack('<QBI',0,2,len(data))+data
        sensor=lambda t:mav.MAVLink_hil_sensor_message(t,*[0.]*13,0x1fff,0).pack(writer)
        host=self.folder/'owner_logs';host.mkdir()
        earlier=b''.join(record(sensor(111000)) for _ in range(10));this=b''.join(record(sensor(222000)) for _ in range(10))
        (host/'wire.bin').write_bytes(earlier+this)
        rows=''.join(f'{n},1,1\n' for n in range(10)).encode();(host/'timing.csv').write_bytes(rows+rows)
        log=self.folder/'new.ulg';log.write_bytes(b'ULog')
        report={'status':'PASS','flight':'PASS','recovery':'PASS','fc_log_before':None,
                'fc_log':{'id':3,'path':str(log),'sha256':hashlib.sha256(b'ULog').hexdigest(),'size':4},
                'host_log':{'dir':str(host),'timing_start':len(rows),'timing_end':2*len(rows),
                            'wire_start':len(earlier),'wire_end':len(earlier)+len(this)},
                'initial_recovery':{'metrics':{'tx_HIL_SENSOR':0},'fc':{'connection_generation':2}},
                'after_model_stop':{'metrics':{'tx_HIL_SENSOR':10},'fc':{'connection_generation':2},'produced_steps':10}}
        sys.path.insert(0,str(PROJECT/'hitl'))
        import host.hitl_run as hr
        from unittest.mock import patch as mock_patch
        real=hr.sha256
        def unreadable(path):
            if Path(path).name=='operations.jsonl':raise PermissionError(f'{path} (injected)')
            return real(path)
        with mock_patch.object(hr,'sha256',side_effect=unreadable):
            code,manifest=self.run_hitl_with('epochs',run_test=self.fixture_flight(report))
        data=manifest['parts']['data'];self.assertEqual(data['verdict'],'PASS',data)
        self.assertEqual((data['wire']['found'],data['wire']['bad_frames'],data['wire']['range']),
                         (10,0,[len(earlier),len(earlier)+len(this)]))
        kept=(next((self.folder/'epochs').glob('run_*'))/'host/wire.bin').read_bytes()
        stamps,i,parser=set(),0,mav.MAVLink(None)
        while i<len(kept):
            n=struct.unpack_from('<QBI',kept,i)[2];stamps|={m.time_usec for m in parser.parse_buffer(kept[i+13:i+13+n]) or []};i+=13+n
        self.assertEqual(stamps,{222000})  # only this run's packets are kept
        self.assertEqual(manifest['parts']['fc_log']['verdict'],'INCOMPLETE')
        self.assertIn('not newer',manifest['parts']['fc_log']['reasons'][0])
        self.assertTrue(any(f.get('error') for f in manifest['files'] if f['path']=='operations.jsonl'))
        self.assertIn('operations.jsonl cannot be read',' '.join(manifest['reasons']));self.assertNotEqual(manifest['verdict'],'PASS')
        # Review 14 R14-2: a count that was not reported is no evidence of 0: the data part is INCOMPLETE.
        for name,change in [('no_start_count',lambda r:r['initial_recovery'].update(metrics={})),
                            ('count_going_back',lambda r:r['initial_recovery'].update(metrics={'tx_HIL_SENSOR':11}))]:
            broken=json.loads(json.dumps(report));change(broken)
            code,manifest=self.run_hitl_with(name,run_test=self.fixture_flight(broken))
            self.assertEqual(manifest['parts']['data']['verdict'],'INCOMPLETE',name)
            self.assertIn('no HIL_SENSOR count',' '.join(manifest['parts']['data']['reasons']),name)
    def test_hitl_run_twice_on_one_owner(self):
        # Review 13 R13-3: two runs on the same owner: each keeps only its own records of the owner's wire.bin.
        self.cli('shutdown','--force-exit');self.host.wait(timeout=10)
        self.host=subprocess.Popen([str(ENTRY),'bridge',*self.common,'--fake-config',str(self.config_path),'--log-dir',
                                    str(self.folder/'logs2'),'--duration','240'],cwd=self.folder,env=self.env,stdout=self.console,stderr=subprocess.STDOUT)
        self.wait(lambda:self.status().get('ready_to_start_model'),8)
        short=['--hold-seconds','1','--hold-timeout','25','--flight-timeout','35']
        runs=[self.hitl_run(*short,expected=3)[0] for _ in range(2)]  # the 1 s Hold makes the flight FAIL
        for manifest in runs:
            data=manifest['parts']['data'];self.assertEqual(data['verdict'],'PASS',data)
            self.assertEqual((data['wire']['found'],data['wire']['bad_frames']),(data['wire']['sensor_packets'],0))
        self.assertGreaterEqual(runs[1]['parts']['data']['wire']['range'][0],runs[0]['parts']['data']['wire']['range'][1])

class HitlRunUnitTests(unittest.TestCase):
    def test_verdict_order_and_real_fc_fixed_flight(self):
        sys.path.insert(0,str(PROJECT/'hitl'))
        from types import SimpleNamespace
        from host.hitl_run import combine,run_hitl
        self.assertEqual(combine(['PASS','INCOMPLETE','PASS']),'INCOMPLETE')
        self.assertEqual(combine(['INCOMPLETE','FAIL','PASS']),'FAIL');self.assertEqual(combine(['PASS']*7),'PASS')
        # Review 13 R13-3/R13-4: one run's records lie between two byte offsets of the owner's wire.bin (sizes
        # taken before model-start and after model-stop); every channel-2 byte in them must be a valid frame.
        from host.hitl_run import wire_slice
        from pymavlink.dialects.v20 import common as mav
        writer=mav.MAVLink(None,srcSystem=2,srcComponent=51)
        sensor=lambda t=0:mav.MAVLink_hil_sensor_message(t,*[0.]*13,0,0).pack(writer)
        record=lambda ch,data:struct.pack('<QBI',0,ch,len(data))+data
        packets=[sensor() for _ in range(5)]
        earlier=b''.join(record(2,sensor(111)) for _ in range(3))+record(1,b'rx')  # an earlier run, then FC bytes
        this=record(2,packets[0]+packets[1][:10])+record(2,packets[1][10:])+record(4,b'cmd')+b''.join(record(2,p) for p in packets[2:])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'wire.bin';path.write_bytes(earlier+this+record(1,b'rx2'))
            a,b=len(earlier),len(earlier)+len(this)
            self.assertEqual(wire_slice(path,a,b),((a,b),5,0))  # a frame split over two records still counts
            self.assertEqual(wire_slice(path,a-3,b+2),((a,b),5,0))  # records cut by an offset are not this run's
            self.assertEqual(wire_slice(path,0,b)[1],8)  # without the start the earlier run's packets would count
            broken=lambda p:p[:-1]+bytes([p[-1]^0xFF])
            other=lambda p:p[:7]+bytes([113])+p[8:]  # message id HIL_GPS, checksum left as it was
            heartbeat=bytearray(mav.MAVLink_heartbeat_message(1,0,0,0,0,3).pack(writer));heartbeat[-1]^=0xFF
            plain=lambda frames:[record(2,p) for p in frames]
            cases={'all bad checksums':plain([broken(p) for p in packets]),
                   'one bad checksum':plain(packets[:2]+[broken(packets[2])]+packets[3:]),
                   'wrong message id':plain(packets[:2]+[other(packets[2])]+packets[3:]),
                   'other bytes in the run':plain(packets[:2])+[record(2,b'\x00\x11junk')]+plain(packets[2:]),
                   'bad frame before the first sensor, same record':[record(2,bytes(heartbeat)+packets[0])]+plain(packets[1:]),
                   'cut off':plain(packets[:4]+[packets[4][:-3]])}
            for name,records in cases.items():
                blob=b''.join(records);path.write_bytes(blob)
                span,found,bad=wire_slice(path,0,len(blob))
                self.assertGreater(bad,0,name);self.assertLessEqual(found,5,name)
            blob=b''.join(record(4 if n==2 else 2,p) for n,p in enumerate(packets));path.write_bytes(blob)  # one on channel 4
            self.assertEqual(wire_slice(path,0,len(blob)),((0,len(blob)),4,0))
        # Review 12 N6: a scenario file that cannot be read stops before any owner call, with a manifest (NOT_RUN).
        import contextlib,io
        import host.hitl_run as hr
        from unittest.mock import patch as mock_patch
        real=hr.sha256
        def missing(path):
            if str(path).endswith('ground.json'):raise FileNotFoundError(path)
            return real(path)
        with tempfile.TemporaryDirectory() as folder:
            args=SimpleNamespace(fake_fc=True,fake_state_dir=Path(folder)/'no_owner',fake_config=None,port='auto',
                                 release=None,out=folder,altitude=None,hold_seconds=None,hold_timeout=None,flight_timeout=None)
            with mock_patch.object(hr,'sha256',side_effect=missing),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_hitl(PROJECT/'hitl',args),2)
            run=next(Path(folder).glob('run_*'))
            manifest=json.loads((run/'manifest.json').read_text())
            self.assertEqual((manifest['verdict'],manifest['parts']['identity']['verdict']),('NOT_RUN','FAIL'))
            self.assertIn('FileNotFoundError',manifest['parts']['identity']['reasons'][0])
            self.assertFalse((run/'operations.jsonl').exists())  # no owner call
        # On a real FC other flight values run too (user 2026-10-18) and are recorded; here no owner runs: NOT_RUN.
        with tempfile.TemporaryDirectory() as folder:
            args=SimpleNamespace(fake_fc=False,fake_state_dir=None,fake_config=None,port='auto',release=None,out=folder,
                                 altitude=50.0,hold_seconds=None,hold_timeout=None,flight_timeout=None)
            with mock_patch.object(hr,'request',side_effect=OSError('no owner')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_hitl(PROJECT/'hitl',args),2)
            manifest=json.loads((next(Path(folder).glob('run_*'))/'manifest.json').read_text())
            self.assertEqual(manifest['scenario']['nonstandard_parameters'],{'altitude':{'requested':50.0,'standard':100}})

if __name__=='__main__':unittest.main(verbosity=2)

import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from host.core import Core
from host.transport import SerialTransport
from host.ipc import Endpoint
from pymavlink.dialects.v20 import common as mav
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);core=Core(ROOT,SerialTransport(ROOT.parent,sys.argv[2] if len(sys.argv)>2 else 'auto'),out,unarmed_only=True);endpoint=Endpoint(core);report={'scope':'unarmed only; no arming/mode/sticks/reboot/parameter changes','status':'NOT_RUN'}
try:
 deadline=time.monotonic()+10
 while not core.status()['ready_to_start_model'] and time.monotonic()<deadline:time.sleep(.05)
 report['before']=core.status()
 if not report['before']['ready_to_start_model']:raise RuntimeError(str(report['before']['missing_conditions']))
 # Read-only output/configuration evidence; never change these parameters.
 for name in ['SYS_AUTOSTART','MAV_SYS_ID','CA_SV_CS0_TYPE','CA_SV_CS1_TYPE','CA_SV_CS2_TYPE','CA_SV_CS3_TYPE',*[f'PWM_SIM_FUNC{k}' for k in range(1,6)],*[f'PWM_MAIN_FUNC{k}' for k in range(1,6)]]:
  core._send_message(mav.MAVLink_param_request_read_message(*core.fc['identity'],name.encode(),-1))
 time.sleep(2);core.start();start=time.monotonic()
 while time.monotonic()-start<30:
  status=core.status()
  if status['model']=='fault' or status['fc']['armed'] is not False:raise RuntimeError(status['last_error'] or 'FC unarmed boundary not confirmed')
  time.sleep(.05)
 report['active_seconds']=time.monotonic()-start;report['active']=core.status();core.stop();stopped=time.monotonic();time.sleep(1.2);report['after_stop']=core.status()
 if report['after_stop']['fc']['heartbeat_at']<=stopped:raise RuntimeError('No fresh post-stop FC heartbeat')
 report['status']='PASS' if report['active']['metrics'].get('rx_HIL_ACTUATOR_CONTROLS',0)>0 and report['active']['produced_steps']>=7400 else 'FAIL'
except Exception as exc:report['status']='FAIL';report['error']=str(exc)
finally:
 core.close(force=True);endpoint.close();report['final']=core.status();(out/'live_unarmed.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if report['status']!='PASS':raise SystemExit(1)

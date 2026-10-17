import argparse,hashlib,json,os,platform,re,shutil,subprocess,sys,uuid
from pathlib import Path
from host.release import platform_id
RUNTIME=Path(__file__).resolve().parent
PLANT=RUNTIME.parent/'plant'
MATLAB=Path('/Applications/MATLAB_R2026b.app')
FLAGS=['-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-fvisibility=hidden','-arch','arm64','-dynamiclib']
# Plant gate reports sealed into every release next to the library validation (validation.json).
GATES=['reuse_policy.json','core_validation.json','plant_validation.json','validation.json']
EVIDENCE=['build.json','core_build.json','core_compile.json']
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fingerprint():
 root=RUNTIME.parent
 files=['FW_SkySurfer_HIL.slx','FW_SkySurfer_InitialFunction.m','PX4_HIL_preload.m','import_aerostates_avl.m','import_aerostates_vsp.m','m_05.mat','m_1.mat','Skysurfer.mat','.satk/reuse-libraries.json']
 records={f:digest(root/f) for f in files}
 # Only the library validator belongs to the build; other tests (GUI, host) do not change the model.
 for folder in ['interface','matlab','native','aircraft/skysurfer']:
  for p in sorted((RUNTIME/folder).rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts:records['hil_runtime/'+str(p.relative_to(RUNTIME))]=digest(p)
 for f in ['poc/source_columns.json','tests/validate_library.py','update.py','host/abi.py','host/scenario.py','host/packets.py']:records['hil_runtime/'+f]=digest(RUNTIME/f)
 # Plant core builder, C Truth, C sensors and their validators (plant/reference holds recorded data, not build inputs).
 for folder in ['include','core','truth','sensors']:
  for p in sorted((PLANT/folder).rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts:records['plant/'+str(p.relative_to(PLANT))]=digest(p)
 # Shipped linked libraries are part of the source build dependency graph.
 old=json.loads((RUNTIME/'reports/phase_a_20261014/dependency_fingerprint.json').read_text())
 records['linked_libraries']={x['path']:digest(x['path']) for x in old.get('mathworks_libraries',[])}
 records['compiler']=subprocess.check_output(['xcrun','clang','--version'],text=True)
 records['architecture']=platform_id();records['compile_flags']=FLAGS
 # Toolchain identity: exact MATLAB update (VersionInfo.xml) and the macOS SDK the compiler uses.
 records['matlab']={'release':'R2026b','version_info_sha256':digest(MATLAB/'VersionInfo.xml')}
 records['sdk']={'path':subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip(),'version':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip()}
 return records
def reference_identity():
 data=PLANT/'reference/data';return {p.name:digest(p) for p in sorted(data.iterdir()) if p.is_file()}
def external_headers(cmd,gen):
 # Every header the library includes from outside the fingerprinted project folders (MATLAB rtw/simulink
 # headers), found by the compiler itself; keys are relative so the build-id does not depend on paths.
 deps=subprocess.check_output(cmd+['-MM'],text=True).replace('\\\n',' ').replace('\\ ','\0').split()
 headers={}
 for token in deps:
  if token.endswith(':') or not token.endswith('.h'):continue
  p=Path(token.replace('\0',' ')).resolve()
  if MATLAB.resolve() in p.parents:headers['MATLAB/'+str(p.relative_to(MATLAB.resolve()))]=digest(p)
  elif gen.resolve() not in p.parents and RUNTIME.parent.resolve() not in p.parents:headers[str(p)]=digest(p)
 return dict(sorted(headers.items()))
def compile_library(cache,fp):
 gen=cache/'codegen/SkySurfer_Core_ert_rtw';out=cache/'native';out.mkdir(exist_ok=True)
 make=(gen/'SkySurfer_Core.mk').read_text();defines=[]
 for key in ['DEFINES_BUILD_ARGS','DEFINES_OPTS','DEFINES_STANDARD']:
  match=re.search(r'^'+key+r'\s*=\s*(.*)$',make,re.M);defines+=match.group(1).split() if match else []
 if '-DMULTI_INSTANCE_CODE=1' not in defines:raise RuntimeError('Generated core is not reusable')
 sources=[gen/x for x in ['SkySurfer_Core.c','SkySurfer_Core_data.c','rtGetInf.c','rtGetNaN.c','rt_nonfinite.c']]
 sources+=[PLANT/'core/sks_core.c',PLANT/'truth/sks_plant.c',PLANT/'sensors/sks_sensors.c',PLANT/'sensors/sks_wmm.c',PLANT/'sensors/sks_wmm_coeffs.c',RUNTIME/'aircraft/skysurfer/adapter.c']
 generated={str(p.relative_to(gen)):digest(p) for p in gen.glob('*') if p.suffix in ['.c','.h']}
 includes=[]
 for inc in [RUNTIME/'interface',PLANT/'include',PLANT/'sensors',gen,MATLAB/'extern/include',MATLAB/'simulink/include',MATLAB/'rtw/c/src',MATLAB/'rtw/c/ert']:includes+=['-I',str(inc)]
 base=['xcrun','clang']+FLAGS+includes+defines+['-DHIL_SOURCE_HASH="'+fp['FW_SkySurfer_HIL.slx']+'"','-DHIL_PLATFORM="macos-arm64"']
 toolchain={'makefile_sha256':digest(gen/'SkySurfer_Core.mk'),'defines':defines,'external_headers':external_headers([x for x in base if x!='-dynamiclib']+[str(p) for p in sources],gen)}
 identity={'fingerprint':fp,'generated':generated,'toolchain':toolchain}
 build_id='skysurfer-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
 cmd=base+['-DHIL_BUILD_ID="'+build_id+'"']+[str(p) for p in sources]+['-o',str(out/'libskysurfer.dylib')];subprocess.run(cmd,check=True)
 compile_worker(out)
 (cache/'results/build.json').write_text(json.dumps({'build_id':build_id,'fingerprint':fp,'generated':generated,'toolchain':toolchain,'command':cmd},indent=2));return build_id
WORKER_SOURCES=['native/macos/worker.c','native/macos/io.c']  # POSIX; macOS and Linux sections inside
def worker_command(out):
 sources=[str(RUNTIME/x) for x in WORKER_SOURCES];inc=['-I',str(RUNTIME/'interface')]
 if sys.platform=='darwin':return ['xcrun','clang','-std=c11','-O2','-fvisibility=hidden','-arch','arm64','-dynamiclib']+inc+sources+['-o',str(out/'libhil_worker.dylib')]
 return ['cc','-std=c11','-O2','-D_GNU_SOURCE','-fvisibility=hidden','-fPIC','-shared','-pthread']+inc+sources+['-lm','-o',str(out/'libhil_worker.so')]
def compile_worker(out):
 cmd=worker_command(out);subprocess.run(cmd,check=True);return Path(cmd[-1]),cmd
def validate_worker(path):
 # FC-only gate: the exports the host needs, a monotonic clock, and the native serial writer on a pipe
 # (bytes delivered in order; a closed descriptor is recorded as EBADF). No model, no MATLAB.
 import errno,time
 sys.path.insert(0,str(RUNTIME));from host.abi import Worker,diagnostics,io_stats
 worker=Worker(path,None);lib=worker.lib;checks={'exports':'PASS'}
 t=[worker.now() for _ in range(1000)];checks['clock_monotonic']='PASS' if all(b>=a for a,b in zip(t,t[1:])) and t[-1]>t[0] else 'FAIL'
 rd,wr=os.pipe();os.set_blocking(rd,False);data=bytes(range(256))*4;got=b''
 try:
  lib.hil_io_start(wr);codes=[lib.hil_io_command(data[k:k+256],256) for k in range(0,len(data),256)];end=time.monotonic()+2
  while len(got)<len(data) and time.monotonic()<end:
   try:got+=os.read(rd,4096)
   except BlockingIOError:time.sleep(.001)
 finally:lib.hil_io_stop();os.close(rd);os.close(wr)
 checks['io_command_order']='PASS' if codes==[0]*4 and got==data else 'FAIL'
 rd,wr=os.pipe();os.close(wr)
 try:
  lib.hil_io_start(wr);lib.hil_io_command(b'bad',3);end=time.monotonic()+1
  while not io_stats(worker)['errors'] and time.monotonic()<end:time.sleep(.001)
  errors=io_stats(worker)['errors'];event=diagnostics(worker)['io_last_event']
 finally:lib.hil_io_stop();os.close(rd)
 checks['io_fatal_errno']='PASS' if errors==1 and event['write_errno']==errno.EBADF else 'FAIL'
 return {'status':'PASS' if all(v=='PASS' for v in checks.values()) else 'FAIL','checks':checks}
def fc_only(cache=None):
 # A release without a model, for platforms where MATLAB code generation is not available (Linux): the owner
 # can talk to the FC (status, readback, logs, SD card); actions that need the model refuse.
 from host.ipc import cache_root
 pid=platform_id();cache=Path(cache or cache_root()/'fc_only_build');(cache/'native').mkdir(parents=True,exist_ok=True)
 path,cmd=compile_worker(cache/'native')
 compiler=subprocess.check_output([cmd[0],'--version'],text=True)
 identity={'platform':pid,'sources':{x:digest(RUNTIME/x) for x in WORKER_SOURCES+['interface/hil_model_api.h','host/abi.py','update.py']},'command':cmd[:-1],'compiler':compiler}
 build_id='fc-only-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
 result=validate_worker(path);(cache/'worker_validation.json').write_text(json.dumps(dict(result,build_id=build_id),indent=2))
 if result['status']!='PASS':raise RuntimeError('Worker validation failed '+json.dumps(result['checks'])+'; active unchanged')
 (cache/'build.json').write_text(json.dumps(dict(identity,build_id=build_id),indent=2))
 parent=RUNTIME/'releases/skysurfer'/pid;parent.mkdir(parents=True,exist_ok=True);staging=parent/('.staging-'+str(uuid.uuid4()));staging.mkdir()
 shutil.copy2(path,staging/path.name);shutil.copy2(RUNTIME/'aircraft/skysurfer/profile.json',staging/'profile.json')
 for name in ['worker_validation.json','build.json']:shutil.copy2(cache/name,staging/name)
 manifest={'schema_version':1,'platform':pid,'build_id':build_id,'abi_version':65537,'library':None,'worker':path.name,'fc_only':True,'gates':{'worker_validation.json':'PASS'},'required_status':'PASS','files':{p.name:digest(p) for p in staging.iterdir()}}
 (staging/'manifest.json').write_text(json.dumps(manifest,indent=2));return install(staging,parent,build_id,pid)
def install(staging,parent,build_id,pid,report=None):
 final=parent/build_id
 if final.exists():raise RuntimeError('Immutable release already exists; active unchanged')
 staging.rename(final);pointer={'schema_version':1,'build_id':build_id,'release':str(final.relative_to(RUNTIME)),'manifest_sha256':digest(final/'manifest.json')}
 active=RUNTIME/'active'/f'{pid}.json';previous=json.loads(active.read_text()) if active.exists() else None
 temporary=active.with_suffix('.tmp');temporary.write_text(json.dumps(pointer,indent=2));os.replace(temporary,active)
 if previous:(RUNTIME/'active'/f'{pid}.previous.json').write_text(json.dumps(previous,indent=2))
 print(json.dumps(dict({'status':'PASS','release':str(final),'build_id':build_id},**(report or {}))));return final
def validate(cache):
 # Plant gates first (core against the reference data, Truth/sensors), then the HIL library itself.
 subprocess.run([sys.executable,'-B',str(PLANT/'core/compile_core.py'),'--cache',str(cache)],check=True)
 for script in ['validate_core.py','validate_plant.py']:subprocess.run([sys.executable,'-B',str(PLANT/'core'/script),'--cache',str(cache)],check=True)
 subprocess.run([sys.executable,'-B',str(RUNTIME/'tests/validate_library.py'),'--cache',str(cache)],check=True)
def publish(cache,build_id,fp,reference):
 # Every gate must have passed, not only the library validation; their reports are sealed in the release.
 gates={}
 for name in GATES:
  path=cache/'results'/name;gates[name]=json.loads(path.read_text()).get('status') if path.is_file() else 'MISSING'
 if any(v!='PASS' for v in gates.values()):raise RuntimeError('Required validation failed or missing '+json.dumps(gates)+'; active unchanged')
 pid=platform_id();parent=RUNTIME/'releases/skysurfer'/pid;parent.mkdir(parents=True,exist_ok=True);staging=parent/('.staging-'+str(uuid.uuid4()));staging.mkdir()
 for f in ['libskysurfer.dylib','libhil_worker.dylib']:shutil.copy2(cache/'native'/f,staging/f)
 shutil.copy2(RUNTIME/'aircraft/skysurfer/profile.json',staging/'profile.json')
 for name in GATES+EVIDENCE:shutil.copy2(cache/'results'/name,staging/name)
 manifest={'schema_version':1,'platform':pid,'build_id':build_id,'abi_version':65537,'library':'libskysurfer.dylib','worker':'libhil_worker.dylib','fingerprint':fp,'gates':gates,'reference':reference,'required_status':'PASS','files':{p.name:digest(p) for p in staging.iterdir()}}
 (staging/'manifest.json').write_text(json.dumps(manifest,indent=2));return install(staging,parent,build_id,pid,{'cache':str(cache)})
def main():
 p=argparse.ArgumentParser();p.add_argument('--cache',type=Path);p.add_argument('--rollback',action='store_true');p.add_argument('--force',action='store_true')
 p.add_argument('--fc-only',action='store_true',help='publish a release without a model (worker only), e.g. on Linux');args=p.parse_args()
 if not args.fc_only and platform_id()!='macos-arm64':raise RuntimeError('Model build/validation runs on macos-arm64 only; use --fc-only here (Windows native build pending on its own host)')
 lock=RUNTIME/'active/update.lock'
 try:fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 except FileExistsError:raise RuntimeError('Another update owns the publish lock; inspect before removing stale lock')
 try:
  os.write(fd,str(os.getpid()).encode());os.close(fd)
  if args.rollback:
   from host.release import read_release
   pid=platform_id();previous=RUNTIME/f'active/{pid}.previous.json';read_release(RUNTIME,previous);temp=RUNTIME/'active/rollback.tmp';temp.write_bytes(previous.read_bytes());os.replace(temp,RUNTIME/f'active/{pid}.json');print('rollback PASS');return
  if args.fc_only:fc_only(args.cache);return
  fp=fingerprint();active=RUNTIME/'active/macos-arm64.json'
  if active.exists() and not args.force and not args.cache:
   from host.release import read_release
   release,manifest=read_release(RUNTIME)
   if manifest['fingerprint']==fp:print(json.dumps({'status':'PASS','unchanged':True,'build_id':manifest['build_id']}));return
  if args.cache:cache=args.cache
  else:
   sys.path.insert(0,str(RUNTIME/'matlab'));from mcp_build import generate
   cache=generate(RUNTIME)
  reference=reference_identity();build_id=compile_library(cache,fp);validate(cache)
  if fingerprint()!=fp:raise RuntimeError('Build dependencies changed during validation; active unchanged')
  if reference_identity()!=reference:raise RuntimeError('Plant reference data changed during validation; active unchanged')
  publish(cache,build_id,fp,reference)
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':
 try:main()
 except Exception as exc:print(str(exc),file=sys.stderr);raise SystemExit(4)

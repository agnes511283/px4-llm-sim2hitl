"""Documented CLI build using the Mac's configured existing MATLAB session."""
import json,queue,subprocess,threading,time
from pathlib import Path
def generate(runtime):
 server=Path.home()/'.matlab/agentic-toolkits/bin/matlab-mcp-server'
 if not server.is_file():raise RuntimeError('Configure this host MATLAB MCP, or run plant/core/build_core.m in MATLAB directly; no runtime reinstall')
 proc=subprocess.Popen([str(server),'--matlab-session-mode','existing','--disable-telemetry','true'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
 messages=queue.Queue()
 def read():
  for line in proc.stdout:
   try:messages.put(json.loads(line))
   except ValueError:pass
 threading.Thread(target=read,daemon=True).start()
 def request(ident,method,params):
  proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':ident,'method':method,'params':params})+'\n');proc.stdin.flush();deadline=time.monotonic()+600
  while time.monotonic()<deadline:
   try:r=messages.get(timeout=1)
   except queue.Empty:
    if proc.poll() is not None:raise RuntimeError('MATLAB MCP exited: '+proc.stderr.read()[-2000:])
    continue
   if r.get('id')==ident:
    if 'error' in r:raise RuntimeError(str(r['error']))
    return r['result']
  raise RuntimeError('MATLAB MCP build timeout')
 try:
  request(1,'initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'SkySurfer-update','version':'1.0'}})
  proc.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');proc.stdin.flush()
  tools=request(2,'tools/list',{})['tools'];tool=next(t for t in tools if t['name']=='evaluate_matlab_code')
  props=tool['inputSchema']['properties'];path=str(Path(runtime).parent/'plant'/'core').replace("'","''")
  # Plant core builder (plant/core/build_core.m): reusable core C plus Simulink reference runs.
  code="addpath('"+path+"'); bcache=build_core(); fprintf('B_EXPORT_CACHE=%s\\n',bcache);"
  args={'code':code}
  if 'project_path' in props:args['project_path']=str(Path(runtime).parent)
  result=request(3,'tools/call',{'name':tool['name'],'arguments':args})
  text='\n'.join(c.get('text','') for c in result.get('content',[]));print(text,flush=True)
  if result.get('isError'):raise RuntimeError('MATLAB build failed')
  import re
  match=re.search(r'B_EXPORT_CACHE=([^\r\n]+)',text)
  if not match:raise RuntimeError('MATLAB did not return export cache')
  return Path(match.group(1))
 finally:
  proc.stdin.close()
  try:proc.wait(timeout=3)
  except subprocess.TimeoutExpired:proc.terminate()

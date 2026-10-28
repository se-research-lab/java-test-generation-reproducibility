"""Replace only the owned loopback display server; never launch experiments."""
import json,subprocess,sys,time,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'monitor/serve_v4.py';new=R/'monitor/serve_v5.py';text=old.read_text(encoding='utf-8').replace('from preview_runner_health_v2 import view_status','from preview_runner_health_v3 import view_status')
assert text!=old.read_text(encoding='utf-8')
with new.open('x',encoding='utf-8') as f:f.write(text)
out=R/'runtime/preview_v5';out.mkdir(exist_ok=False)
parent=psutil.Process(23352);assert abs(parent.create_time()-1792986794.092808)<.01 and str(old) in parent.cmdline()
assert not parent.children(recursive=True),'Unexpected display-server child; refuse stop'
before={'pid':parent.pid,'create_time':parent.create_time(),'script_sha256':sha(old)}
parent.terminate();before['exit_code']=parent.wait(timeout=10)
stdout=(out/'stdout.txt').open('xb');stderr=(out/'stderr.txt').open('xb')
try:p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(new)],cwd=R,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
finally:stdout.close();stderr.close()
identity={'pid':p.pid,'create_time':psutil.Process(p.pid).create_time(),'script':str(new),'script_sha256':sha(new),'health_source_sha256':sha(R/'src/preview_runner_health_v3.py'),'previous_server':before,'started_utc':datetime.now(timezone.utc).isoformat(),'scope':'display only; no experiment endpoints'};dump(out/'owner.json',identity)
status=None
for attempt in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=2) as response:status=json.load(response)
  if status.get('monitor_implementation')=='read_only_v5_gradle_aware':break
 except (OSError,ValueError):pass
 time.sleep(.2)
assert status and status.get('monitor_implementation')=='read_only_v5_gradle_aware','New display server not verified'
checks={}
for name,url,method,host,expected in [('status','/status.json','GET',None,200),('manifest','/manifest.json','GET',None,200),('no_files','/src/run_gradle_full40_v2.py','GET',None,404),('no_post','/','POST',None,501),('foreign_host','/status.json','GET','example.invalid',403)]:
 request=urllib.request.Request('http://127.0.0.1:8766'+url,method=method,headers={'Host':host} if host else {})
 try:
  with urllib.request.urlopen(request,timeout=3) as response:code=response.status
 except urllib.error.HTTPError as ex:code=ex.code
 assert code==expected,(name,code);checks[name]=code
dump(out/'http_checks.json',{'status':'PASS_HTTP_ONLY','checks':checks,'browser_render_checked':False,'new_experiment_calls':0})
audit.log('B1_GRADLE_PREVIEW_V5_READY',owner_sha256=sha(out/'owner.json'),http_checks_sha256=sha(out/'http_checks.json'),experiment_endpoints=False)
print(json.dumps({'server_pid':p.pid,'http_checks':checks,'experiment_calls':0},indent=2))

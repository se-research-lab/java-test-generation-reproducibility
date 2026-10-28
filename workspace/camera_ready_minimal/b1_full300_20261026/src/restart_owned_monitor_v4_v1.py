"""Replace only the positively identified loopback monitor, never a runner."""
import json,os,socket,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

out=R/'runtime/monitor_v4_launch_v1'
assert not out.exists(),'No implicit server relaunch'
prepared=json.loads((R/'validation/monitor_v4_preparation_v1/result.json').read_text(encoding='utf-8'))
server=R/'monitor/serve_v4.py'
assert prepared['server_sha256']==sha(server) and prepared['helper_sha256']==sha(R/'src/preview_runner_health_v2.py')
previous=json.loads((R/'runtime/monitor_v3_launch_v1/started.json').read_text(encoding='utf-8-sig'))
proc=psutil.Process(previous['pid'])
args=proc.cmdline()
assert Path(proc.exe()).resolve()==Path(sys.executable).resolve()
assert args[1:]==['-B','-X','utf8',str(R/'monitor/serve_v3.py')]
identity={'pid':proc.pid,'create_time':proc.create_time(),'script':str(R/'monitor/serve_v3.py')}
out.mkdir(parents=True,exist_ok=False)
dump(out/'plan.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'scope':'read-only loopback monitor replacement only',
     'old_monitor':identity,'new_server_sha256':sha(server),'new_experiments':0,'GPT_API_calls':0,
     'reason':'Display owner PID/create-time/script and plan hashes for new v6 invocation; no experiment endpoint'})
assert psutil.Process(identity['pid']).create_time()==identity['create_time']
proc.terminate()
proc.wait(timeout=10)
with socket.socket() as sock:
    sock.bind(('127.0.0.1',8766))
argv=[sys.executable,'-B','-X','utf8',str(server)]
with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
    child=subprocess.Popen(argv,cwd=R,stdin=subprocess.DEVNULL,stdout=so,stderr=se,
          creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS)
dump(out/'started.json',{'pid':child.pid,'create_time':psutil.Process(child.pid).create_time(),
     'at_utc':datetime.now(timezone.utc).isoformat(),'script':str(server),'new_experiments':0})
audit.log('B1_READONLY_MONITOR_REPLACED_VERIFIED_OLD_PID',old_monitor=identity,new_pid=child.pid,server_sha256=sha(server),
          experiments_stopped_or_started=0,GPT_API_calls=0)
print(json.dumps({'monitor_pid':child.pid,'experiments_stopped_or_started':0}))

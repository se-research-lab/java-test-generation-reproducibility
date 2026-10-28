"""Real owned Python child-process checks only. No Java/Maven/Gradle/GPT."""
import json,sys,subprocess
from pathlib import Path
import psutil
from process_supervisor_v1 import Supervisor,environment,sha,dump,R,GuardAbort
O=R/'validation/process_supervisor_v1';O.mkdir(parents=True,exist_ok=False);checks=[]
def script(name,code):
 out=O/name;out.mkdir();p=out/'fixture.py';p.write_text(code,encoding='utf-8');return out,p
def execute(out,p,timeout=10):
 s=Supervisor(out,environment(),mode='fixture');return s,s.run([sys.executable,'-B','-X','utf8',str(p)],out,timeout,sha(sys.executable),{str(p.resolve()):sha(p)})
out,p=script('normal',"print('fixture stdout',flush=True)\nimport sys\nprint('fixture stderr',file=sys.stderr,flush=True)\n")
s,r=execute(out,p);assert r.returncode==0 and 'fixture stdout' in r.stdout and 'fixture stderr' in r.stderr;checks.append('stdout_stderr_preserved')
out,p=script('nonzero',"print('failure evidence',flush=True)\nraise SystemExit(7)\n")
s,r=execute(out,p);assert r.returncode==7 and 'failure evidence' in r.stdout;checks.append('nonzero_exit_kept')
out,p=script('timeout',"import time\nprint('before timeout',flush=True)\ntime.sleep(30)\n")
try:execute(out,p,1)
except subprocess.TimeoutExpired as e:assert 'before timeout' in e.stdout;checks.append('timeout_preserves_output')
else:raise AssertionError('Timeout not enforced')
record=json.loads((out/'commands/001/finished.json').read_text());assert record['reason']=='TIMEOUT' and record['termination']['terminated_pids'];checks.append('only_owned_timeout_PID_recorded')
out,p=script('stop_tree',"import subprocess,sys,time,json\nfrom pathlib import Path\nchild=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\nPath('child_pid.json').write_text(json.dumps({'pid':child.pid}))\nprint('before stop',flush=True)\nPath('STOP_REQUESTED.json').write_text('{}')\ntime.sleep(30)\n")
try:execute(out,p)
except GuardAbort:checks.append('midflight_stop_propagates_without_retry')
else:raise AssertionError('Stop not enforced')
record=json.loads((out/'commands/001/finished.json').read_text());child=json.loads((out/'child_pid.json').read_text())['pid']
assert child in record['termination']['terminated_pids'] and not psutil.pid_exists(child);assert (out/'commands/001/stdout.txt').read_text().startswith('before stop');checks.append('owned_descendant_stopped_and_evidence_kept')
out,p=script('prestop',"raise AssertionError('must not execute')\n");(out/'STOP_REQUESTED.json').write_text('{}')
try:execute(out,p)
except GuardAbort:assert not list((out/'commands').iterdir());checks.append('prestop_no_spawn')
else:raise AssertionError('Prestop ignored')
out,p=script('no_admission',"raise AssertionError('must not execute')\n");s=Supervisor(out,environment())
try:s.run([sys.executable,'-B','-X','utf8',str(p)],out,1,sha(sys.executable),{})
except GuardAbort:assert not list((out/'commands').iterdir());checks.append('benchmark_without_admission_no_spawn')
else:raise AssertionError('Admission bypass')
report={'status':'PASS','checks':checks,'Python_fixture_processes_started':5,'Java_calls':0,'GPT_API_calls':0,'benchmark_admitted':False,'supervisor_sha256':sha(R/'src/process_supervisor_v1.py')}
dump(O/'result.json',report);print(json.dumps(report,indent=2))

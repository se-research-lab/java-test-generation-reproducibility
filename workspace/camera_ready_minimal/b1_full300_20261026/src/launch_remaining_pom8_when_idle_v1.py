"""One finite launch after the previous offline audit releases the worker mutex."""
import json,sys,subprocess,time,msvcrt,psutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from projection_io_v1 import publish_json
A=R/'completion_amendment_v1';O=A/'remaining_pom8_launch_v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 O.mkdir(exist_ok=False);me=psutil.Process();admission=A/'admission_maven_pom_v3.json';h=sha(admission)
 dump(O/'owner.json',{'pid':me.pid,'create_time':me.create_time(),'started_utc':now(),'admission_sha256':h,'scope':'launch only the eight unattempted POM classes; no retry112; one child invocation'})
 publish_json(R/'runtime/completion_progress.json',{'phase':'QUEUED_REMAINING_POM8','active_index':None,'remaining_indices':[119,163,173,211,220,269,275,294],'reason':'waiting previous offline audit to release mutex','updated_utc':now(),'GPT_API_calls':0,'full300_complete':False},label='remaining_pom8_queue')
 while True:
  if (R/'STOP_REQUESTED.json').exists():dump(O/'stopped.json',{'at_utc':now(),'reason':'STOP','new_experiment_calls':0});return
  assert sha(admission)==h,'Admission drift while queued'
  with (R/'runtime/dispatcher.lock').open('r+b') as f:
   try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   except OSError:pass
   else:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);break
  time.sleep(2)
 argv=[sys.executable,'-B','-X','utf8',str(R/'src/complete_maven_groups_v4.py'),'--group','pom'];dump(O/'plan.json',{'argv':argv,'runner_sha256':sha(R/'src/complete_maven_groups_v4.py'),'at_utc':now(),'automatic_retry':False})
 with (O/'stdout.txt').open('xb') as so,(O/'stderr.txt').open('xb') as se:
  child=subprocess.Popen(argv,stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
  dump(O/'child.json',{'pid':child.pid,'create_time':psutil.Process(child.pid).create_time(),'started_utc':now()});rc=child.wait()
 dump(O/'complete.json',{'returncode':rc,'finished_utc':now(),'stdout_sha256':sha(O/'stdout.txt'),'stderr_sha256':sha(O/'stderr.txt'),'automatic_retry':False,'full300_complete':False});print('Remaining POM8 invocation finished',rc,flush=True)
if __name__=='__main__':main()

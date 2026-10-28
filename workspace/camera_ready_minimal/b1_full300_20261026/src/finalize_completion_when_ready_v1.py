"""Authorized finite post-batch queue: offline audit, history, private package. No generation."""
import json,subprocess,sys,time,msvcrt,psutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1';O=A/'automatic_finalization_v1';B=R.parent/'paired49_20261023'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 O.mkdir(exist_ok=False);me=psutil.Process();dump(O/'owner.json',{'pid':me.pid,'create_time':me.create_time(),'script_sha256':sha(__file__),'started_utc':now(),'scope':'wait finite authorized stage sequence, then offline evidence delivery; no experiment calls'})
 # A missing completion receipt must never trigger a new benchmark or an implicit restart.
 while not (A/'stage_sequence_v1/complete.json').exists():
  if (R/'STOP_REQUESTED.json').exists():dump(O/'stopped.json',{'reason':'STOP','at_utc':now()});return
  time.sleep(2)
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   receipts=[]
   for label,script,args in [('audit','audit_completion_results_v3.py',['--output','analysis_v1']),('history','export_completion_history_v1.py',[]),('package','package_completion_evidence_v2.py',[])]:
    path=R/'src'/script;argv=[sys.executable,'-B','-X','utf8',str(B/'audit.py'),'run','completion_final_'+label+'_v1',sys.executable,'-B','-X','utf8',str(path),*args]
    dump(O/(label+'_plan.json'),{'argv':argv,'script_sha256':sha(path),'created_utc':now(),'automatic_retry':False})
    with (O/(label+'.stdout.txt')).open('xb') as so,(O/(label+'.stderr.txt')).open('xb') as se:rc=subprocess.run(argv,stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW).returncode
    row={'stage':label,'returncode':rc,'at_utc':now(),'stdout_sha256':sha(O/(label+'.stdout.txt')),'stderr_sha256':sha(O/(label+'.stderr.txt'))};receipts.append(row);dump(O/(label+'_finished.json'),row);print(json.dumps(row),flush=True)
    if rc:dump(O/'interrupted.json',{'receipts':receipts,'automatic_retry':False,'reason':'offline finalization stage failed; no new benchmark'});return
   stat=json.loads((A/'analysis_v1/statistics.json').read_text());dump(O/'complete.json',{'receipts':receipts,'full300_complete':stat['full300_complete'],'unresolved_indices':stat['unresolved_indices'],'finished_utc':now(),'GPT_API_calls':0,'new_experiment_calls_in_finalizer':0,'paper_updated':False})
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()

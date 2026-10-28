"""Finite authorized queue, no implicit retries; qualification then conditional admission."""
import json,msvcrt,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1';O=A/'maven_sequence_v3'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 O.mkdir(exist_ok=False)
 dump(O/'start.json',{'created_utc':now(),'script_sha256':sha(__file__),'scope':'wait current Gradle worker, then two synthetic qualifications and only passed groups; no retry','GPT_calls':0})
 while True:
  if (R/'STOP_REQUESTED.json').exists():raise RuntimeError('STOP')
  with (R/'runtime/dispatcher.lock').open('r+b') as f:
   try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   except OSError:pass
   else:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);break
  time.sleep(2)
 receipts=[]
 for group in ['pom','junit3']:
  for stage,script,args in [('qualification','qualify_maven_completion_v3.py',['--kind',group]),('seal','seal_completion_maven_v3.py',['--group',group]),('benchmark','complete_maven_groups_v2.py',['--group',group])]:
   if (R/'STOP_REQUESTED.json').exists():raise RuntimeError('STOP')
   argv=[sys.executable,'-B','-X','utf8',str(R/'src'/script),*args];label=group+'_'+stage
   dump(O/(label+'_plan.json'),{'argv':argv,'script_sha256':sha(R/'src'/script),'created_utc':now(),'automatic_retry':False})
   with (O/(label+'.stdout.txt')).open('xb') as so,(O/(label+'.stderr.txt')).open('xb') as se:
    rc=subprocess.run(argv,stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW).returncode
   receipt={'group':group,'stage':stage,'returncode':rc,'finished_utc':now(),'stdout_sha256':sha(O/(label+'.stdout.txt')),'stderr_sha256':sha(O/(label+'.stderr.txt'))};receipts.append(receipt);dump(O/(label+'_finished.json'),receipt);print(json.dumps(receipt),flush=True)
   if rc:break
 dump(O/'complete.json',{'finished_utc':now(),'receipts':receipts,'automatic_retry':False,'full300_complete':False})
if __name__=='__main__':main()

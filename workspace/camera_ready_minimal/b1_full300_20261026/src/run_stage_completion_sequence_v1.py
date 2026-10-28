"""Finite two-group queue; no automatic retry on failed stages."""
import json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1';O=A/'stage_sequence_v1'
def main():
 O.mkdir(exist_ok=False);receipts=[]
 for group in ['junit3','pom']:
  for stage,script in [('seal','seal_stage_completion_v2.py'),('benchmark','complete_maven_groups_v3.py')]:
   if (R/'STOP_REQUESTED.json').exists():raise RuntimeError('STOP')
   argv=[sys.executable,'-B','-X','utf8',str(R/'src'/script),'--group',group];n=group+'_'+stage;dump(O/(n+'_plan.json'),{'argv':argv,'sha256':sha(R/'src'/script),'retry':False})
   with (O/(n+'.stdout.txt')).open('xb') as so,(O/(n+'.stderr.txt')).open('xb') as se:rc=subprocess.run(argv,stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW).returncode
   row={'group':group,'stage':stage,'returncode':rc,'finished_utc':datetime.now(timezone.utc).isoformat()};dump(O/(n+'_finished.json'),row);receipts.append(row);print(json.dumps(row),flush=True)
   if rc:break
 dump(O/'complete.json',{'receipts':receipts,'full300_complete':False,'automatic_retry':False})
if __name__=='__main__':main()

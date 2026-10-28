"""Manual future entry point. Explicit resume flag required; never scheduled automatically."""
import argparse,json,sys,subprocess,psutil,msvcrt
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1';O=A/'pause_20261027_after173_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--explicit-user-resume',action='store_true');args=parser.parse_args()
 if not args.explicit_user_resume:
  print('PAUSED. This command requires a later explicit user request and --explicit-user-resume. No file released and no experiment started.');return
 # This path is invoked only by the human or an assistant after a NEW human resume request.
 checkpoint=load(O/'checkpoint.json');admission=load(O/'resume_admission_v1.json');assert admission['resume_checkpoint_sha256']==sha(O/'checkpoint.json')
 assert admission['admitted_sample_indices']==checkpoint['remaining_indices']==[211,220,269,275,294]
 assert not (A/'maven_pom_resume_after173_v1').exists(),'Existing resume attempt requires inspection; do not restart'
 assert not (O/'resume_invocation').exists(),'No implicit second invocation'
 verify_pins(load(O/'checkpoint_pins.json'));verify_pins(admission['code_and_input_hashes']);verify_pins(admission['tool_hashes'])
 assert sha(A/'admission_maven_pom_v3.json')==checkpoint['admission_sha256']
 for row in load(O/'accepted25.json'):assert row['must_not_rerun'] and row['index'] not in admission['admitted_sample_indices']
 for i in admission['admitted_sample_indices']:assert not (R/'jobs'/f'{i:03d}_completion_pom_resume_after173_v1').exists()
 with (R/'runtime/dispatcher.lock').open('r+b') as f:
  f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
 # Refuse to resume alongside any scoped Java experiment process.
 for proc in psutil.process_iter(['name','cmdline']):
  try:
   if (proc.info['name'] or '').lower()=='java.exe':assert str(R).lower() not in ' '.join(proc.info['cmdline'] or []).lower(),'Existing scoped Java process'
  except (psutil.NoSuchProcess,psutil.AccessDenied):continue
 stop=R/'STOP_REQUESTED.json';assert stop.exists();request=load(stop);assert Path(request['pause_request']).resolve()==(O/'pause_request.json').resolve()
 assert sha(stop)==checkpoint['STOP_requested_sha256']
 # Preserve the STOP evidence via same-volume rename; both exact paths are inside R.
 released=O/('STOP_released_on_explicit_resume_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
 assert stop.resolve()==(R/'STOP_REQUESTED.json').resolve() and released.resolve().is_relative_to(O.resolve()) and not released.exists()
 invocation=O/'resume_invocation';invocation.mkdir(exist_ok=False)
 dump(invocation/'authorization.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'explicit_flag':True,'remaining_indices':admission['admitted_sample_indices'],'accepted25_excluded':True,'parent_policy_unchanged':True,'queue_follow_on_authorized':False})
 stop.rename(released)
 argv=[sys.executable,'-B','-X','utf8',str(R/'src/run_remaining5_after173_v1.py'),'--group','pom']
 dump(invocation/'plan.json',{'argv':argv,'STOP_evidence_preserved':str(released),'automatic_retry':False})
 with (invocation/'stdout.txt').open('xb') as so,(invocation/'stderr.txt').open('xb') as se:
  child=subprocess.Popen(argv,stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
  dump(invocation/'owner.json',{'pid':child.pid,'create_time':psutil.Process(child.pid).create_time()});rc=child.wait()
 dump(invocation/'complete.json',{'returncode':rc,'at_utc':datetime.now(timezone.utc).isoformat(),'automatic_retry':False,'follow_on_queues_started':False});print('Explicit resume invocation finished',rc,flush=True)
if __name__=='__main__':main()

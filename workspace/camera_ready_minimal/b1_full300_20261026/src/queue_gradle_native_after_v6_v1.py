"""One dependency-bound continuation, not a schedule or automatic retry.
Only after the new current153 checkpoint succeeds: one synthetic fixture.
This is component qualification during an idle window, not Maven260 completion.
Never generates tests, calls GPT, admits Gradle40 or edits the manuscript.
"""
import json,msvcrt,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump,GuardAbort
from process_supervisor_v1 import environment
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
OUT=R/'runtime/gradle_native_after_v6_v1'
COMPLETION=R/'runtime/remaining_maven153_v6_completion.json'
VERSIONS=['2.13']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def eligible(record,expected_plan_hash):
 if not isinstance(record,dict):return False
 if type(record.get('exit_code')) is not int or record['exit_code']!=0:return False
 if type(record.get('jobs_finished_this_invocation')) is not int or record['jobs_finished_this_invocation']!=153:return False
 a,b=record.get('new_scored_this_invocation'),record.get('new_deferred_this_invocation')
 if type(a) is not int or type(b) is not int or min(a,b)<0 or a+b!=153:return False
 if type(record.get('new_policy_accepted')) is not int or record['new_policy_accepted']!=46+a:return False
 deferred=record.get('unscored_deferred_indices')
 if not isinstance(deferred,list) or any(type(i) is not int for i in deferred) or len(set(deferred))!=len(deferred):return False
 fixed={48,49,72,112,119,163,173,211,220,269,275,294}
 if not fixed.issubset(deferred) or len(deferred)!=12+b:return False
 if record['new_policy_accepted']+len(deferred)!=211:return False
 return (record.get('automatic_resume') is False and record.get('error') is None
         and record.get('full300_complete') is False and record.get('Gradle_benchmark_admitted') is False
         and type(record.get('GPT_API_calls')) is int and record['GPT_API_calls']==0
         and record.get('launch_plan_sha256')==expected_plan_hash)
def pins_match(pins):return all(Path(p).is_file() and sha(p)==h for p,h in pins.items())
def state(name,**extra):
 value={'at_utc':now(),'state':name,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0,'automatic_retry':False,**extra}
 receipt=publish_json(OUT/'state.json',value,label='gradle_fixture_queue');audit.log('B1_GRADLE_V6_SYNTHETIC_CONTINUATION_STATE',state=name,receipt=receipt,**extra);return value
def ui_phase(name):
 # Never publish concurrently with a benchmark writer.
 with (R/'runtime/dispatcher.lock').open('r+b') as lock:
  try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:return False
  try:
   s=load(R/'status.json');s.update(phase=name,updated_utc=now(),running=0,active_sample_index=None,benchmark_admitted=False,Gradle_benchmark_admitted=False,Gradle_fixture_only=True)
   s['blockers']=['Chỉ qualify native measurement bằng suite tổng hợp đã lưu; không chạy Gradle40','EvoSuite Gradle generation/provider trên corpus vẫn cần nghiệm thu','GPT, repeated subset và manuscript giữ nguyên']
   return publish_json(R/'status.json',s,label='gradle_fixture_stage')['published']
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
def main():
 assert not OUT.exists(),'Existing continuation is never restarted automatically'
 prepared=load(R/'validation/gradle_native_fixture_preparation_v1/result.json')
 runner=R/'src/run_gradle_native_fixture_v1.py';assert prepared['status']=='PASS_PREPARATION_ONLY' and prepared['source_sha256']==sha(runner)
 assert not (R/'validation/gradle_native_runtime_fixture_v1').exists(),'Native runtime fixture already exists; review it rather than retry'
 maven_plan=R/'launch_remaining_maven153_v6.json';assert maven_plan.is_file()
 names=['queue_gradle_native_after_v6_v1.py','run_gradle_native_fixture_v1.py','gradle_native_recipe_v4.py','gradle_command_policy_v2.py','gradle_process_supervisor_v2.py','process_supervisor_v1.py','maven_adapter_v1.py','maven_controller_v2.py','measurement_parser_v1.py','projection_io_v1.py']
 paths=[R/'src'/n for n in names]+[R/'validation/gradle_native_fixture_preparation_v1/result.json',R/'validation/gradle_native_recipe_v4/result.json',R/'admission_maven_v6.json',R/'inputs/gradle40_context_v2/manifest.json',maven_plan]
 pins={str(p.resolve()):sha(p) for p in paths};OUT.mkdir(exist_ok=False)
 plan={'created_utc':now(),'scope':'one continuation one Gradle2.13 synthetic measurement fixture after clean completion and dispatcher unlock of current153 Maven invocation; unscored classes remain, NOT Maven260 or full300 completion','Maven_completion_path':str(COMPLETION),'expected_Maven_launch_plan_sha256':sha(maven_plan),'versions':VERSIONS,'max_wait_seconds':43200,'source_pins':pins,'rules':['stop on global STOP or local CANCEL','skip entirely if Maven did not complete successfully','no retries after any fixture failure or busy lock','fixtures use saved synthetic suite, no generation','never admit Gradle40 or modify G0/paper'],'new_EvoSuite_calls':0,'GPT_API_calls':0}
 dump(OUT/'plan.json',plan);state('WAITING_FOR_CURRENT153_CLEAN_COMPLETION')
 deadline=time.monotonic()+plan['max_wait_seconds'];invalid_reads=0
 while True:
  if (R/'STOP_REQUESTED.json').exists() or (OUT/'CANCEL_REQUESTED.json').exists():state('CANCELLED_BEFORE_NEXT_STAGE');return 0
  if COMPLETION.exists():
   try:completion=load(COMPLETION)
   except json.JSONDecodeError:
    invalid_reads+=1
    if invalid_reads>=5:state('STOPPED_INVALID_COMPLETION_RECORD');return 1
    time.sleep(.2);continue
   if not eligible(completion,plan['expected_Maven_launch_plan_sha256']):state('SKIPPED_CURRENT153_NOT_CLEANLY_COMPLETE');return 0
   if not pins_match(pins):state('STOPPED_SOURCE_PIN_DRIFT');return 1
   with (R/'runtime/dispatcher.lock').open('r+b') as idle:
    try:idle.seek(0);msvcrt.locking(idle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:time.sleep(2);continue
    else:idle.seek(0);msvcrt.locking(idle.fileno(),msvcrt.LK_UNLCK,1)
   break
  if time.monotonic()>=deadline:state('EXPIRED_NO_FIXTURE_STARTED');return 0
  time.sleep(2)
 state('CURRENT153_CLEAN_COMPONENT_QUALIFICATION_READY',completion_sha256=sha(COMPLETION))
 for version in VERSIONS:
  if (R/'STOP_REQUESTED.json').exists() or (OUT/'CANCEL_REQUESTED.json').exists():state('CANCELLED_BEFORE_NEXT_STAGE');return 0
  if not pins_match(pins):state('STOPPED_SOURCE_PIN_DRIFT');return 1
  state('SYNTHETIC_MEASUREMENT_FIXTURE_STARTING',Gradle_version=version)
  ui_phase('GRADLE_NATIVE_MEASUREMENT_FIXTURE_ONLY / '+version)
  folder=OUT/('gradle_'+version);folder.mkdir()
  argv=[sys.executable,'-B','-X','utf8',str(runner),'--version',version]
  dump(folder/'command_plan.json',{'argv':argv,'runner_sha256':sha(runner),'new_benchmark_classes':0,'generation_authorized':False})
  try:
   with (folder/'stdout.txt').open('xb') as so,(folder/'stderr.txt').open('xb') as se:
    result=subprocess.run(argv,cwd=R,env=environment(),stdin=subprocess.DEVNULL,stdout=so,stderr=se,shell=False,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   dump(folder/'finished.json',{'at_utc':now(),'returncode':result.returncode,'stdout_sha256':sha(folder/'stdout.txt'),'stderr_sha256':sha(folder/'stderr.txt'),'automatic_retry':False})
   if result.returncode!=0:
    state('STOPPED_FIXTURE_FAILED_OR_BUSY_NO_RETRY',Gradle_version=version,returncode=result.returncode);ui_phase('GRADLE_FIXTURE_REVIEW_REQUIRED / '+version);return 1
   output=R/'validation/gradle_native_runtime_fixture_v1'/('gradle_'+version)/'result.json';record=load(output)
   assert record['status']=='PASS_SYNTHETIC_NATIVE_MEASUREMENT_ONLY' and record['Gradle_benchmark_admitted'] is False and record['new_EvoSuite_calls']==record['GPT_API_calls']==0
   state('SYNTHETIC_MEASUREMENT_COMPONENT_PASSED',Gradle_version=version,result_sha256=sha(output));ui_phase('GRADLE_NATIVE_COMPONENT_PASS_NO_BENCHMARK / '+version)
  except BaseException as ex:
   dump(folder/'controller_failure.json',{'at_utc':now(),'error_type':type(ex).__name__,'detail':str(ex),'traceback':traceback.format_exc(),'automatic_retry':False})
   state('STOPPED_CONTROLLER_ERROR_NO_RETRY',Gradle_version=version,error_type=type(ex).__name__);ui_phase('GRADLE_FIXTURE_REVIEW_REQUIRED / '+version);raise
 state('ONE_SYNTHETIC_COMPONENT_PASSED_NOT_CORPUS_ADMISSION');ui_phase('GRADLE213_NATIVE_COMPONENT_PASS_OTHER_WRAPPERS_AND_GENERATION_PENDING');return 0
if __name__=='__main__':sys.exit(main())

"""One serial pass over admitted Gradle40; no automatic restart or repair.
Every terminal or deferred output is retained. Existing E49/Maven/GPT untouched.
"""
import json,msvcrt,sys,shutil,traceback
from pathlib import Path
from datetime import datetime,timezone
import psutil
from maven_adapter_v1 import R,sha,dump,GuardAbort
from gradle_command_policy_v3 import CONTEXT
from gradle_execution_v2 import execute
from prepare_sandbox_v1 import prepare
from maven_controller_v2 import archive
from parallel_pin_verify_v1 import verify_pins
from run_maven_b1_v3 import guards
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
A=R/'admission_gradle_full40_v1.json';O=R/'runtime/gradle_full40_v1'
PUBLIC=('sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status')
DEFER_ONLY=('Offline/toolchain environment unavailable; retain unscored, do not repair or zero-fill','Measurement dependency audit unavailable; do not score or repair','Existing non-JUnit4/ambiguous runtime; no upgrade or dependency repair','Prior native EvoSuite tests require separate provenance review; no silent deletion')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def output(i):return R/'jobs'/f'{i:03d}_gradle_v1'
def verify_archive(folder):
 rows=load(folder/'artifact_manifest.json');verify_pins({str(folder/r['relative']):r['sha256'] for r in rows})
def project(state,active=None):
 rows=load(R/'runtime/manifest_live300.json');terminal=[];deferred=[];unattempted=[];calls=0
 for row in rows:
  if row['build_tool']!='gradle':continue
  i=row['sample_index_1based'];folder=output(i)
  for p in (folder/'commands').glob('*/plan.json'):
   if '-jar' in load(p)['argv'] and (p.parent/'started.json').exists():calls+=1
  if (folder/'result.json').exists():
   result=load(folder/'result.json');terminal.append(i);row['status']='COMPLETED_E1_GRADLE' if result['legacy_process_build'] else 'TERMINAL_PIPELINE_FAILURE'
  elif (folder/'deferred.json').exists():deferred.append(i);row['status']='DEFERRED_GRADLE_UNSCORED'
  elif (folder/'interrupted.json').exists():row['status']='INTERRUPTED_REVIEW_REQUIRED'
  elif i!=active:unattempted.append(i);row['status']='PENDING_GRADLE_LOCKED_V1'
  if i==active:row['status']='RUNNING'
 status=load(R/'status.json');status.update(phase='GRADLE V1 / '+state,updated_utc=now(),new_completed=191+len(terminal),new_policy_accepted=191+len(terminal),running=int(active is not None),active_sample_index=active,gradle_pending=40-len(terminal),gradle_unattempted=len(unattempted),gradle_deferred_unscored=len(deferred),gradle_terminal=len(terminal),gradle_deferred_sample_indices=deferred,maven_pending=20,maven_deferred_unscored=20,maven_unattempted=0,new_API_calls=0,benchmark_EvoSuite_calls=216+calls,new_EvoSuite_calls=216+calls+status['fixture_EvoSuite_calls'],Gradle_benchmark_admitted=True,benchmark_admitted=True,GPT_guard='PASS',reuse49_guard='PASS',disk_free_GB=round(shutil.disk_usage(R).free/1e9,2))
 status['blockers']=['Cấu hình Gradle v1 đã khóa trước class đầu tiên; không sửa sau lỗi','20 Maven deferred/unscored giữ nguyên; chưa được gọi full300 hoàn tất','Mọi Gradle environment/guard failure giữ bằng chứng; GPT và E0 không chạy lại']
 status['tasks'][3].update(status='DONE',name='Gradle4wrapper và controller synthetic đã nghiệm thu')
 status['tasks'][4].update(status='DONE',name='Khóa Gradle v1 trước40class; seeds/budget E49')
 status['tasks'][5].update(status='IN_PROGRESS',name='Chạy Gradle40 theo thứ tự gốc; không sửa cấu hình/test sau lỗi')
 mr=publish_json(R/'runtime/manifest_live300.json',[{k:r[k] for k in PUBLIC} for r in rows],label='gradle_v1_manifest')
 sr=publish_json(R/'status.json',status,label='gradle_v1_status')
 if not mr['published'] or not sr['published']:audit.log('B1_GRADLE_UI_PUBLICATION_FAILED_EXPERIMENT_CONTINUES',manifest=mr,status=sr)

def main():
 lock=load(A);assert lock['execution_scope']=='benchmark' and lock['Gradle_benchmark_admitted'] and lock['GPT_generation_authorized'] is False
 assert lock['code_and_input_hashes'][str(Path(__file__).resolve())]==sha(__file__),'Runner not sealed'
 assert not O.exists(),'Existing invocation must be inspected; no automatic restart'
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   guards(load(R/'admission_maven_v6.json'));verify_pins(lock['code_and_input_hashes'])
   contexts={r['sample_index_1based']:r for r in load(CONTEXT)};metadata={r['sample_index_1based']:r for r in load(R/'inputs/context251_v1/manifest.json')};jobs=[j for j in load(R/'manifest300.json') if j['build_tool']=='gradle']
   assert [j['sample_index_1based'] for j in jobs]==lock['admitted_sample_indices'] and len(jobs)==40
   assert all(not output(j['sample_index_1based']).exists() for j in jobs),'No rerun or implicit resume of prior Gradle job'
   O.mkdir(exist_ok=False);me=psutil.Process();dump(O/'owner.json',{'pid':me.pid,'create_time':me.create_time(),'script':str(Path(__file__).resolve()),'script_sha256':sha(__file__),'admission_sha256':sha(A),'started_utc':now(),'automatic_resume':False})
   finished=[];deferred=[];project('STARTING')
   for j in jobs:
    i=j['sample_index_1based'];folder=output(i)
    if (R/'STOP_REQUESTED.json').exists():raise GuardAbort('STOP; no new class')
    guards(load(R/'admission_maven_v6.json'));verify_pins(lock['code_and_input_hashes'])
    assert sha(A)==load(O/'owner.json')['admission_sha256'],'Admission changed mid-batch'
    context=contexts[i];m=metadata[i];job={**j,**{k:m[k] for k in ['selected_test_fqcn','package','junit_version','testng_version']}}
    def event(kind,**kw):
     with (folder/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kw},ensure_ascii=False)+'\n')
     audit.log('B1_GRADLE_V1_'+kind,sample_index=i,**kw)
     if kind in {'STAGE','COMMAND_STARTED'}:project('RUNNING / '+str(kw.get('stage',kind)),i)
    try:
     prepare(i,folder,R/'inputs/snapshot_v3')
     dump(folder/'job_admission.json',{'batch_admission_sha256':sha(A),'job':job,'context_sha256':sha(CONTEXT),'started_utc':now(),'attempt_policy':'one frozen lifecycle; optional predeclared same-seed technical generation retry only'})
     project('RUNNING',i);result=execute(folder,job,context,A,event);verify_archive(folder);finished.append(i)
     print(json.dumps({'sample_index':i,'terminal':True,'generation_calls':result['generation_calls'],'process_gate':result['legacy_process_build'],'strict_mutation':result['legacy_strict_mutation_percent']}),flush=True)
    except GuardAbort as ex:
     if str(ex) not in DEFER_ONLY:raise
     dump(folder/'deferred.json',{'sample_index_1based':i,'class_key':j['class_key'],'at_utc':now(),'reason':str(ex),'terminal':False,'score':None,'rerun_authorized':False,'configuration_changed':False,'GPT_API_calls':0})
     if not (folder/'artifact_manifest.json').exists():archive(folder)
     verify_archive(folder);deferred.append(i);audit.log('B1_GRADLE_V1_CLASS_DEFERRED_UNSCORED',sample_index=i,reason=str(ex),policy_unchanged=True)
     print(json.dumps({'sample_index':i,'deferred_unscored':True,'reason':str(ex)}),flush=True)
    guards(load(R/'admission_maven_v6.json'));project('CHECKPOINT')
   source_cache=Path('C:/Users/admin/.gradle')
   original_cache_rows=load(R/'cache_preparation_gradle_v1/recovery_v2/manifest.json')
   verify_pins({str((source_cache/r['relative']).resolve()):r['sha256'] for r in original_cache_rows})
   receipt={'all_original_cache_files_unchanged':True,'status':'ONE_PASS_COMPLETED','finished_utc':now(),'admission_sha256':sha(A),'terminal_indices':finished,'deferred_unscored_indices':deferred,'attempted_or_preflight_checked':len(finished)+len(deferred),'automatic_resume':False,'GPT_API_calls':0,'full300_complete':False,'Maven_deferred_preserved':20}
   dump(O/'complete.json',receipt);project('ONE_PASS_COMPLETED');audit.log('B1_GRADLE_V1_PASS_COMPLETE',receipt_sha256=sha(O/'complete.json'),terminal=len(finished),deferred=len(deferred));print(json.dumps(receipt,indent=2))
  except BaseException as ex:
   if O.exists():
    dump(O/'interrupted.json',{'at_utc':now(),'type':type(ex).__name__,'detail':str(ex),'traceback':traceback.format_exc(),'auto_resume':False,'configuration_repair_authorized':False})
    if 'folder' in locals() and folder.exists() and not (folder/'artifact_manifest.json').exists():
     dump(folder/'interrupted.json',{'at_utc':now(),'type':type(ex).__name__,'detail':str(ex),'score_accepted':False,'auto_resume':False});archive(folder)
    project('STOPPED_REVIEW_REQUIRED')
   audit.log('B1_GRADLE_V1_INVOCATION_STOPPED',error_type=type(ex).__name__,detail=str(ex),automatic_resume=False);raise
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()

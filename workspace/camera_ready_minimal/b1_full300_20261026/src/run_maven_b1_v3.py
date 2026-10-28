"""Serial Maven continuation: CP-file transport and independent UI publication.
Requires a newly sealed v3 admission; preserves every earlier job and failure.
"""
import argparse,json,msvcrt,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,GuardAbort,sha,dump
from b1_maven_commands_v3 import MavenCommands
from maven_controller_v2 import execute,archive,bytecode,ensure
from prepare_sandbox_v1 import prepare
from checkpoint_archive_guard_v2 import verify
from projection_io_v1 import publish_json
from run_maven_b1_v2 import guards
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
RECOVER={i:'jobs/'+f'{i:03d}'+'_cpfile_v3' for i in [12,16,23]}
PUBLIC=('sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def selected_result(index):
 if index==3:return R/'jobs/003_native_junit_diagnostic_v3/diagnostic_result.json'
 if index in RECOVER and (R/RECOVER[index]/'result.json').exists():return R/RECOVER[index]/'result.json'
 return R/'jobs'/f'{index:03d}'/'result.json'
def counters():
 planned=started=0
 folders=list((R/'jobs').glob('[0-9][0-9][0-9]'))+[R/p for p in RECOVER.values()]
 for out in folders:
  for plan in (out/'commands').glob('*/plan.json'):
   if '-jar' in load(plan)['argv']:
    planned+=1;started+=(plan.parent/'started.json').exists()
 fixture=2+sum(1 for p in (R/'validation/long_classpath_fixture_v1/commands').glob('*/plan.json') if '-jar' in load(p)['argv'] and (p.parent/'started.json').exists())
 return planned,started,fixture
def project(state,active=None):
 """UI I/O failure is reported separately from experimental outcomes."""
 try:
  jobs=load(R/'manifest300.json');terminal=accepted=0;pending_recovery=[]
  for j in jobs:
   i=j['sample_index_1based'];base=R/'jobs'/f'{i:03d}';out=R/RECOVER[i] if i in RECOVER else base
   if (base/'result.json').exists() or (out/'result.json').exists():
    terminal+=1
    if i in RECOVER and (not (out/'result.json').exists() or (out/'interrupted.json').exists()):pending_recovery.append(i)
    elif not (out/'interrupted.json').exists():accepted+=1
    result=selected_result(i)
    if result.exists():j['status']='COMPLETED_E1_MAVEN' if load(result)['legacy_process_build'] else 'TERMINAL_PIPELINE_FAILURE'
   if i==active:j['status']='RUNNING'
   elif (out/'interrupted.json').exists():j['status']='INTERRUPTED_REVIEW_REQUIRED'
   elif i in pending_recovery:j['status']='PENDING_MAVEN_QUALIFICATION'
  planned,started,fixture=counters();s=load(R/'status.json')
  s.update(phase='MAVEN V3 / '+state,updated_utc=now(),new_completed=terminal,new_policy_accepted=accepted,pending_transport_recovery=pending_recovery,running=int(active is not None),active_sample_index=active,maven_pending=211-terminal,maven_policy_pending=211-accepted,gradle_pending=40,new_API_calls=0,benchmark_admitted=True,benchmark_EvoSuite_calls=started,benchmark_EvoSuite_commands_planned=planned,benchmark_EvoSuite_commands_not_started=planned-started,fixture_EvoSuite_calls=fixture,new_EvoSuite_calls=started+fixture,GPT_guard='PASS',GPT_guard_checked_utc=now(),reuse49_guard='PASS',disk_free_GB=round(shutil.disk_usage(R).free/1e9,2),ui_technical_hold=False,automatic_v2_resume=False)
  s['tasks'][5].update(status='IN_PROGRESS',name='Maven v3: CP-file có điều kiện, recovery12/16/23 và original order')
  s['blockers']=[f'Transport recovery chưa hoàn tất: {pending_recovery}', 'Gradle launcher4 PASS; build/provider fixture chưa qualify; chưa admit40', 'E1-full300 chưa hoàn tất; GPT và paper giữ khóa']
  public=[{k:j[k] for k in PUBLIC} for j in jobs];manifest=R/'runtime/manifest_live300.json'
  same=manifest.exists() and load(manifest)==public
  mr={'published':True,'unchanged':True} if same else publish_json(manifest,public,label='maven_v3_manifest')
  sr=publish_json(R/'status.json',s,label='maven_v3_status') if mr['published'] else {'published':False,'reason':'manifest publication failed; retain prior status'}
  if not mr['published'] or not sr['published']:audit.log('B1_UI_PUBLICATION_FAILED_EXPERIMENT_CONTINUES',manifest=mr,status=sr)
  return mr['published'] and sr['published']
 except OSError as ex:
  audit.log('B1_UI_IO_FAILED_EXPERIMENT_CONTINUES',error_type=type(ex).__name__,detail=str(ex));return False

class RecoveryCommands(MavenCommands):
 """Verify the same compiled input and ordered CP before any recovery spawn."""
 def verify_classpath(self,cp):
  old=R/'jobs'/f"{self.job['sample_index_1based']:03d}";module=self.out/'repo'/self.job['module']
  ensure(load(old/'production_generation_baseline.json')==bytecode(module),'Recovery production bytecode differs from pre-spawn failure')
  ensure(load(old/'controller_source_before.json')==load(self.out/'controller_source_before.json'),'Recovery source input differs')
  plans=[load(p) for p in (old/'commands').glob('*/plan.json') if '-jar' in load(p)['argv']]
  ensure(len(plans)==1,'Recovery must have exactly one prior unstarted generation plan')
  oldcp=plans[0]['argv'][plans[0]['argv'].index('-projectCP')+1]
  import os
  expected=[str(self.out/'repo'/Path(x).resolve().relative_to((old/'repo').resolve())) if Path(x).resolve().is_relative_to((old/'repo').resolve()) else x for x in oldcp.split(os.pathsep)]
  if self.generations==1:ensure(cp.split(os.pathsep)==expected,'Recovery ordered classpath differs beyond owned repo relocation')
  path=super().verify_classpath(cp)
  dump(self.out/f'recovery_input_equivalence_{self.generations:02d}.json',{'status':'PASS_BEFORE_EVO_START','original_job':str(old),'original_result_sha256':sha(old/'result.json'),'production_bytecode':'IDENTICAL','source_input':'IDENTICAL','ordered_CP':'IDENTICAL_EXCEPT_OWNED_REPO_RELOCATION' if self.generations==1 else 'EXACT_E49_CONDITIONAL_SANITIZED_RETRY_VALIDATED_BY_BASE_GUARD','seed':self.job['seed'],'CP_guard_sha256':sha(path)})
  return path
def reseal(out):
 old=out/'artifact_manifest.json'
 if old.exists():
  dest=out/'artifact_manifest_before_interrupt.json';ensure(not dest.exists(),'Archive interrupt backup already exists');old.rename(dest)
 archive(out)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--max-jobs',type=int,required=True);args=parser.parse_args();ensure(1<=args.max_jobs<=211,'Invalid max jobs')
 path=R/'admission_maven_v3.json';lock=load(path);guards(lock)
 ensure(lock['recovery_folders']=={str(k):v for k,v in RECOVER.items()},'Unexpected recovery plan')
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   jobs=load(R/'manifest300.json');contexts={j['sample_index_1based']:j for j in load(R/'inputs/context251_v1/manifest.json')};count=0
   for j in jobs:
    i=j['sample_index_1based']
    if i not in lock['admitted_sample_indices']:continue
    base=R/'jobs'/f'{i:03d}';out=R/RECOVER[i] if i in RECOVER else base
    if (out/'interrupted.json').exists():raise GuardAbort('Interrupted job requires explicit review: '+str(out))
    if i==3:verify(base);verify(R/'jobs/003_native_junit_diagnostic_v3');continue
    if (out/'result.json').exists():verify(out);continue
    if out.exists():raise GuardAbort('Incomplete owned job; no implicit retry: '+str(out))
    guards(lock)
    if i in RECOVER:
     verify(base);old=load(base/'result.json');ensure(not old['generation_success'] and not old['measurement_attempted'],'Recovery outside launch-only failure')
     ensure(not any((p.parent/'started.json').exists() for p in (base/'commands').glob('*/plan.json') if '-jar' in load(p)['argv']),'Prior EvoSuite actually started; not eligible for recovery')
    context=contexts[i];job={**j,**{k:context[k] for k in ['junit_version','testng_version','package','selected_test_fqcn']}};commands=None
    def event(kind,**kw):
     with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kw},ensure_ascii=False)+'\n')
     audit.log('B1_MAVEN_V3_'+kind,sample_index=i,**kw)
     if kind=='COMMAND_STARTED':project('RUNNING',i)
    try:
     prepare(i,out,R/'inputs/snapshot_v3');dump(out/'job_admission.json',{'batch_admission_sha256':sha(path),'job':job,'recovery_of':str(base) if i in RECOVER else None,'started_utc':now()});project('RUNNING',i)
     commands=(RecoveryCommands if i in RECOVER else MavenCommands)(out,job,path,event)
     result=execute(out,job,commands,event);verify(out);guards(lock);count+=1;project('CHECKPOINT')
     print(json.dumps({'completed_this_invocation':count,'sample_index':i,'recovery':i in RECOVER,'gate':result['legacy_process_build'],'strict_score':result['legacy_strict_mutation_percent'],'generation_plans':commands.generations,'GPT_API_calls':0}),flush=True)
    except BaseException as ex:
     if out.exists():dump(out/'interrupted.json',{'at_utc':now(),'error_type':type(ex).__name__,'detail':str(ex),'auto_resume':False,'score_accepted':False});reseal(out)
     project('STOPPED_FOR_REVIEW');audit.log('B1_MAVEN_V3_INTERRUPTED',sample_index=i,error_type=type(ex).__name__,detail=str(ex));raise
    if count>=args.max_jobs:break
   project('CHECKPOINT_NO_AUTOMATIC_RESUME');audit.log('B1_MAVEN_V3_INVOCATION_COMPLETE',completed=count,max_jobs=args.max_jobs)
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()

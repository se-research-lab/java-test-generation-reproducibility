"""Serial bounded dispatcher. Each invocation has explicit --max-jobs; no auto-resume."""
import argparse,json,sys,shutil,os,msvcrt,importlib.util
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,GuardAbort,sha,dump
from b1_maven_commands_v2 import MavenCommands
from maven_controller_v1 import execute,archive
from prepare_sandbox_v1 import prepare
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def guards(lock):
 if (R/'STOP_REQUESTED.json').exists():raise GuardAbort('Explicit STOP; no new job')
 for p,h in lock['code_and_input_hashes'].items():
  if sha(p)!=h:raise GuardAbort('Code/input drift: '+p)
 for row in load(R/'audit/input_lock.json'):
  if sha(row['path'])!=row['sha256']:raise GuardAbort('Original input drift')
 spec=importlib.util.spec_from_file_location('b1gptguard',R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
 if g.collect()!=load(g.LOCK):raise GuardAbort('GPT guard drift')
 for reg in ['measurement49_camera_ready_registry_v1.json','camera_ready_response_registry_v1.json','disclosure_only_registry_v1.json']:
  for row in load(B/'audit'/reg)['files']:
   if sha(B/row['path'])!=row['sha256']:raise GuardAbort('Accepted E49/paper evidence drift')
 audit.verify()
 if shutil.disk_usage(R).free<lock['minimum_free_bytes']:raise GuardAbort('Disk reserve reached')
def project(state,job=None):
 folder=R/'runtime';folder.mkdir(exist_ok=True);seq=len(list((folder/'status_backups').glob('*.json')))+1;old=R/'status.json'
 backup=folder/'status_backups'/f'{seq:06d}.json';backup.parent.mkdir(exist_ok=True)
 with old.open('rb') as f,backup.open('xb') as t:shutil.copyfileobj(f,t)
 jobs=load(R/'manifest300.json');done=[];active=None;calls=0
 for j in jobs:
  out=R/'jobs'/f"{j['sample_index_1based']:03d}"
  if (out/'result.json').exists():
   r=load(out/'result.json');done.append(r);calls+=r['generation_calls'];j['status']='COMPLETED_E1_MAVEN' if r['legacy_process_build'] else 'TERMINAL_PIPELINE_FAILURE'
  elif (out/'interrupted.json').exists():j['status']='INTERRUPTED_REVIEW_REQUIRED'
  elif out.exists():j['status']='RUNNING' if job==j['sample_index_1based'] and state=='RUNNING' else 'INCOMPLETE_REVIEW_REQUIRED';active=j['sample_index_1based']
 # Count admitted generation commands actually started, including an interrupted current job.
 started=0
 for plan in (R/'jobs').glob('*/commands/*/plan.json'):
  if (plan.parent/'started.json').exists() and '-jar' in load(plan)['argv']:started+=1
 s=load(old);s.update(updated_utc=now(),phase='MAVEN B1 / '+state,new_completed=len(done),running=int(state=='RUNNING'),maven_pending=211-len(done),gradle_pending=40,benchmark_admitted=True,new_API_calls=0,fixture_EvoSuite_calls=2,new_EvoSuite_calls=2+started,benchmark_EvoSuite_calls=started,active_sample_index=job,GPT_guard='PASS',GPT_guard_checked_utc=now())
 s['tasks'][2]['status']='DONE';s['tasks'][2]['name']='Maven controller và input đã nghiệm thu'
 s['tasks'][4]['name']='Maven controller fixture PASS; Gradle chưa qualify';s['tasks'][5]['status']='IN_PROGRESS'
 s['blockers']=['Maven211 đang thực hiện theo thứ tự gốc; failures được giữ','Gradle40 chưa admission; cần wrapper/JDK/gate/timeout mapping','Chưa đủ E1-full300 để phân tích hoặc sửa paper']
 dump(folder/f'status_{seq:06d}.json',s);temp=folder/'status_projection.tmp';dump(temp,s);temp.replace(old)
 temp=folder/'manifest_projection.tmp';dump(temp,jobs);temp.replace(folder/'manifest_live300.json')
def main():
 p=argparse.ArgumentParser();p.add_argument('--max-jobs',type=int,required=True);a=p.parse_args();assert 1<=a.max_jobs<=211
 path=R/'admission_maven_v1.json';lock=load(path);guards(lock)
 runtime=R/'runtime';runtime.mkdir(exist_ok=True)
 with (runtime/'dispatcher.lock').open('a+b') as file:
  file.seek(0,2)
  if not file.tell():file.write(b'0');file.flush()
  file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
  try:
   jobs=load(R/'manifest300.json');contexts={x['sample_index_1based']:x for x in load(R/'inputs/context251_v1/manifest.json')};count=0
   for j in jobs:
    i=j['sample_index_1based']
    if i not in lock['admitted_sample_indices']:continue
    out=R/'jobs'/f'{i:03d}'
    if (out/'result.json').exists():
     if not (out/'artifact_manifest.json').exists():raise GuardAbort('Result without complete archive; explicit reconciliation required')
     continue
    if out.exists():raise GuardAbort('Unfinished job exists; no implicit retry: '+str(i))
    guards(lock);context=contexts[i];job={**j,**{k:context[k] for k in ['junit_version','testng_version','package','selected_test_fqcn']}}
    commands=None
    def event(kind,**kw):
     with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'timestamp_utc':now(),'kind':kind,**kw},ensure_ascii=False)+'\n');f.flush()
     audit.log('B1_MAVEN_'+kind,sample_index=i,**kw)
     if kind=='COMMAND_STARTED':project('RUNNING',i)
    try:
     prepare(i,out,R/'inputs/snapshot_v3');dump(out/'job_admission.json',{'batch_admission_sha256':sha(path),'job':job,'started_utc':now()});project('RUNNING',i)
     commands=MavenCommands(out,job,path,event);result=execute(out,job,commands,event)
     guards(lock);count+=1;project('CHECKPOINT',None)
     print(json.dumps({'completed_this_invocation':count,'sample_index':i,'class_key':j['class_key'],'gate':result['legacy_process_build'],'generation_calls':result['generation_calls'],'score':result['legacy_strict_mutation_percent'],'GPT_API_calls':0}),flush=True)
    except BaseException as ex:
     if out.exists():
      dump(out/'interrupted.json',{'timestamp_utc':now(),'error_type':type(ex).__name__,'detail':str(ex),'generation_calls':commands.generations if commands else 0,'auto_resume':False,'score_assigned':(out/'result.json').exists()})
      if not (out/'artifact_manifest.json').exists():archive(out)
     project('STOPPED_FOR_REVIEW',None);audit.log('B1_MAVEN_INTERRUPTED',sample_index=i,error_type=type(ex).__name__,detail=str(ex));raise
    if count>=a.max_jobs:break
   project('CHECKPOINT_NO_AUTOMATIC_RESUME',None);audit.log('B1_MAVEN_INVOCATION_COMPLETE',completed=count,max_jobs=a.max_jobs)
  finally:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()

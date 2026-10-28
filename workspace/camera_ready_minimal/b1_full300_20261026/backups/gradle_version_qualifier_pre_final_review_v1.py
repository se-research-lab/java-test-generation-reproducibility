"""Four exact --version commands only, with NONBLOCK dispatcher lock.

PREPARED ONLY until explicitly invoked. This does not qualify builds, native
JUnit providers, test generation, PIT/JaCoCo fixtures or Gradle40 benchmarks.
"""
import json,msvcrt,os,re,sys,time,shutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,JDK,GuardAbort,sha,dump
from gradle_command_policy_v2 import CONTEXT,PRIVATE_HOME,launcher_paths,command_hash,ensure
from gradle_process_supervisor_v2 import GradleSupervisor,environment
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
OUT=R/'validation/gradle_versions_qualification_v1'
CACHE=R/'cache_preparation_gradle_v1'
COMPLETE=CACHE/'recovery_v2/complete.json'
MANIFEST=CACHE/'recovery_v2/manifest.json'

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def cache_verify(rows,home):
 count=0;total=0
 for row in rows:
  p=home/row['relative'];ensure(p.is_file() and not p.is_symlink(),'Missing/link cache input: '+row['relative'])
  ensure(p.resolve().is_relative_to(home.resolve()),'Cache path outside root')
  ensure(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'Cache content drift: '+row['relative'])
  count+=1;total+=row['bytes']
 return {'status':'PASS','files':count,'bytes':total,'manifest_sha256':sha(MANIFEST)}
def archive(folder):
 files=[]
 for p in sorted(folder.rglob('*')):
  if p.is_file() and p.name!='artifact_manifest.json':files.append({'relative':p.relative_to(folder).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
 dump(folder/'artifact_manifest.json',files)

def qualified(lockfile):
 ensure(not OUT.exists(),'No overwrite/resume of a completed or interrupted qualification')
 ensure(not (R/'STOP_REQUESTED.json').exists(),'Explicit B1 stop')
 completed=load(COMPLETE);summary=load(R/'inputs/gradle40_context_v2/summary.json');static=load(R/'validation/gradle_command_policy_v2/result.json')
 ensure(completed['status']=='PASS_PRIVATE_CACHE_PREPARATION_ONLY' and completed['runtime_qualified'] is False,'Private cache preparation not PASS')
 ensure(Path(completed['private_Gradle_user_home']).resolve()==PRIVATE_HOME.resolve(),'Wrong prepared private home')
 ensure(summary['status']=='PASS_METADATA_ONLY' and static['status']=='PASS_STATIC_ONLY','Metadata/static guard prerequisite missing')
 ensure(sha(CONTEXT)==summary['manifest_sha256'] and sha(MANIFEST)==completed['manifest_sha256'],'Manifest prerequisite hash drift')
 contexts=load(CONTEXT);jobs={r['sample_index_1based']:r for r in load(R/'manifest300.json')}
 selected={}
 for context in sorted(contexts,key=lambda r:r['sample_index_1based']):selected.setdefault(context['Gradle_version'],context)
 ensure(set(selected)=={'2.13','5.2.1','6.9.4','8.14.4'},'Version inventory differs')
 chosen=sorted(selected.values(),key=lambda r:r['sample_index_1based'])
 rows=load(MANIFEST);ensure(len(rows)==completed['files'],'Cache manifest row count differs')
 for name in ['init.gradle','init.gradle.kts','init.d','gradle.properties']:
  ensure(not (PRIVATE_HOME/name).exists(),'Unexpected private user configuration/init input: '+name)
 ensure(shutil.disk_usage(R).free>12_000_000_000,'Disk reserve reached')
 before=cache_verify(rows,PRIVATE_HOME);audit.verify()
 codepaths=[Path(__file__),R/'src/gradle_command_policy_v2.py',R/'src/gradle_process_supervisor_v2.py',R/'src/process_supervisor_v1.py',R/'src/maven_adapter_v1.py',R/'validation/gradle_command_policy_v2/result.json',R/'audit/gradle_qualification_sources_v2.json',CONTEXT,R/'inputs/gradle40_context_v2/summary.json',R/'manifest300.json',COMPLETE,MANIFEST,CACHE/'recovery_v2/protocol.json']
 pins={str(p.resolve()):sha(p) for p in codepaths}
 # All copied distribution files, including docs/samples/markers, are pinned.
 for row in rows:
  if row['relative'].startswith('wrapper/dists/'):pins[str((PRIVATE_HOME/row['relative']).resolve())]=row['sha256']
 launchers=launcher_paths();java=(JDK/'bin/java.exe').resolve();tools={str(p):sha(p) for p in [java,*launchers.values()]}
 ensure(all(p.is_file() for p in launchers.values()),'Prepared launcher missing')
 for launcher in launchers.values():
  initdir=launcher.parents[1]/'init.d'
  ensure(not any(p.suffix.lower() in {'.gradle','.kts'} for p in initdir.rglob('*') if p.is_file()),'Distribution contains an executable init script')
 ensure(len(chosen)==4 and all(jobs[c['sample_index_1based']]['build_tool']=='gradle' for c in chosen),'Chosen metadata does not identify Gradle40')
 OUT.mkdir(parents=True,exist_ok=False);dump(OUT/'cache_before.json',before)
 admissions=[];results=[];commands_started=0
 protocol={'created_utc':now(),'scope':'four local launcher --version commands only; no build/fixture/provider/benchmark admission','dispatcher_lock_acquired_nonblocking':True,'lockfile':str(lockfile),'private_home':str(PRIVATE_HOME),'JDK':str(JDK),'selected_contexts':[{'sample_index_1based':c['sample_index_1based'],'version':c['Gradle_version'],'class_key':c['class_key'],'build_root':c['build_root_relative_to_repo'],'module_dir':c['module_dir_relative_to_repo']} for c in chosen],'cache_complete_sha256':sha(COMPLETE),'cache_manifest_sha256':sha(MANIFEST),'code_and_distribution_hashes':pins,'tools':tools,'Gradle_benchmark_admitted':False,'GPT_generation_authorized':False,'new_EvoSuite_calls':0,'timeout_each_seconds':30,'automatic_retry':False,'init_scripts':None,'offline':True,'daemon_policy':'--no-daemon; owned process tree only'}
 dump(OUT/'protocol.json',protocol)
 try:
  for context in chosen:
   version=context['Gradle_version'];job=jobs[context['sample_index_1based']];out=OUT/('gradle_'+version);repo=out/'repo';build=(repo/context['build_root_relative_to_repo']);module=repo/context['module_dir_relative_to_repo']
   build.mkdir(parents=True,exist_ok=False);module.mkdir(parents=True,exist_ok=True)
   ensure(not any(p.is_file() for p in repo.rglob('*')),'Version qualification repository must be empty')
   argv=[str(launchers[version]),'--offline','--no-daemon','-g',str(PRIVATE_HOME.resolve()),'--version']
   admission={'schema':'B1_gradle_supervisor_v2','Gradle_execution_admitted':True,'execution_scope':'runtime_qualification','Gradle_runtime_qualified':False,'Gradle_benchmark_admitted':False,'GPT_generation_authorized':False,'supervisor_sha256':sha(R/'src/gradle_process_supervisor_v2.py'),'base_supervisor_sha256':sha(R/'src/process_supervisor_v1.py'),'command_policy_sha256':sha(R/'src/gradle_command_policy_v2.py'),'gradle_user_home':str(PRIVATE_HOME.resolve()),'gradle_launchers':{k:str(v) for k,v in launchers.items()},'java_executable':str(java),'tool_hashes':tools,'gradle_context_path':str(CONTEXT.resolve()),'gradle_context_sha256':sha(CONTEXT),'admitted_sample_indices':[context['sample_index_1based']],'code_and_input_hashes':pins,'gradle_task_plans':{'version':{'argv_tail':['--version'],'timeout_seconds':30}},'allowed_command_hashes':[command_hash(argv,build,30)],'init_script':None,'generation_authorized':False}
   path=out/'runtime_qualification_admission.json';dump(path,admission);admissions.append({'version':version,'path':str(path),'sha256':sha(path)})
   def event(kind,**kwargs):
    nonlocal commands_started
    if kind=='COMMAND_STARTED':commands_started+=1
    with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kwargs},ensure_ascii=False)+'\n')
    audit.log('B1_GRADLE_VERSION_'+kind,Gradle_version=version,**kwargs)
   supervisor=GradleSupervisor(out,environment(),job,context,path,event)
   result=supervisor.run(argv,build,30,tools[str(launchers[version])],{},stage='version')
   text=result.stdout+'\n'+result.stderr
   ensure(result.returncode==0,'Gradle --version nonzero exit: '+version)
   ensure(re.search(r'^Gradle '+re.escape(version)+r'\s*$',text,re.MULTILINE) is not None,'Reported Gradle version differs: '+version)
   ensure('1.8.0_172' in text and ('JVM:' in text or 'Launcher JVM:' in text),'Reported JVM is not pinned JDK8u172: '+version)
   ensure(not any(p.is_file() for p in repo.rglob('*')),'Version command changed owned empty repository')
   record={'status':'PASS_VERSION_COMMAND_ONLY','Gradle_version':version,'sample_index_metadata_context':context['sample_index_1based'],'reported_JVM':'1.8.0_172','returncode':result.returncode,'command_started_count':len(supervisor.records),'source_guard':'PASS_EMPTY_REPOSITORY_UNCHANGED','fixture_provider_qualified':False,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0}
   dump(out/'result.json',record);results.append(record)
  after=cache_verify(rows,PRIVATE_HOME);dump(OUT/'cache_after.json',after)
  # Original shared cache is only READ here; every copied source hash must match.
  source=Path(load(CACHE/'protocol.json')['source']);source_after=cache_verify(rows,source);dump(OUT/'source_cache_after.json',source_after)
  audit.verify()
  complete={'status':'PASS_VERSION_COMMANDS_ONLY','finished_utc':now(),'versions':[r['Gradle_version'] for r in results],'Gradle_version_commands_started':commands_started,'JVM_verified':'1.8.0_172','private_cache_copied_bytes_unchanged':True,'original_source_cache_bytes_unchanged':True,'empty_repository_source_guards':'PASS','runtime_launcher_qualification_only':True,'build_fixture_qualified':False,'native_provider_qualified':False,'EvoSuite_Gradle_generation_qualified':False,'Gradle_benchmark_admitted':False,'GPT_API_calls':0,'new_EvoSuite_calls':0,'automatic_retry':False,'admission_files':admissions,'protocol_sha256':sha(OUT/'protocol.json')}
  dump(OUT/'complete.json',complete);archive(OUT)
  audit.log('B1_GRADLE_VERSION_QUALIFICATION_COMPLETE',complete_sha256=sha(OUT/'complete.json'),artifact_manifest_sha256=sha(OUT/'artifact_manifest.json'),Gradle_commands=commands_started,benchmark_admitted=False,GPT_API_calls=0)
  print(json.dumps(complete,indent=2));return 0
 except BaseException as ex:
  failure={'status':'FAILED_QUALIFICATION_PRESERVE_LOGS','at_utc':now(),'error_type':type(ex).__name__,'detail':str(ex),'Gradle_commands_started':commands_started,'Gradle_benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0,'auto_resume':False}
  dump(OUT/'interrupted.json',failure);archive(OUT);audit.log('B1_GRADLE_VERSION_QUALIFICATION_FAILED',**failure);raise

def main():
 lockfile=R/'runtime/dispatcher.lock'
 if not lockfile.is_file():
  print('NOT_STARTED: dispatcher lock file missing; no files/directories/processes created');return 2
 with lockfile.open('r+b') as file:
  try:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:
   print('NOT_STARTED: dispatcher busy; no qualification files/directories/processes created');return 2
  try:return qualified(lockfile)
  finally:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':sys.exit(main())

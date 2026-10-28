"""E-only Gradle lifecycle candidate. Import-only; requires sealed admission.

No source/native repair, dependency version upgrade, outcome-driven retry,
network fallback, or cohort selection. Actual stage outcomes remain separate
from unsupported environment/guard failures. This file grants no execution.
"""
import json,os,re,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,JDK,WORKSPACE,sha,dump,GuardAbort,reviewer_options,native_suite,generation_bindings
from gradle_command_policy_v3 import CONTEXT,PRIVATE_HOME,launcher_paths,command_hash,ensure
from gradle_process_supervisor_v5 import GradleSupervisor,environment
from gradle_generation_argv_v1 import checked_gradle_generation_argv
from gradle_native_recipe_v7 import VERSIONS,validate_config,main_audit_script,measurement_script
from classpath_transport_v1 import prepare as prepare_transport,argv_sha256
from maven_controller_v2 import source_hashes,archive
from gradle_measurement_parser_v1 import parse
from parallel_pin_verify_v1 import verify_pins

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()

def phase_recipe(config,out,phase):
 ensure(phase in {'main_audit','measure'},'Unknown recipe phase')
 validate_config(config);folder=out/'recipes'/phase;folder.mkdir(parents=True,exist_ok=False);(folder/'evidence').mkdir()
 text=(main_audit_script if phase=='main_audit' else measurement_script)(config,folder)
 p=folder/'init.gradle'
 with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
 dump(folder/'recipe.json',{'source_sha256':sha(R/'src/gradle_native_recipe_v7.py'),'config':config,'phase':phase,'init_sha256':sha(p),'scope':'requires enclosing sealed Gradle admission'})
 return p,folder/'evidence'

def classify_environment_failure(result):
 text=((result.stdout or '')+'\n'+(result.stderr or '')).lower()
 return any(s in text for s in ['no cached version','no cached resource','no cached module','available for offline mode','no repositories are defined','requires java 11','requires java 17','could not determine java version'])

class Commands:
 def __init__(self,out,job,context,admission,event):
  self.out=Path(out).resolve();self.job=job;self.context=context;self.admission=Path(admission).resolve();self.lock=load(admission);self.event=event;self.generations=0
  ensure(self.lock.get('GPT_generation_authorized') is False,'GPT prohibited')
  scope=self.lock.get('execution_scope');ensure(scope in {'runtime_qualification','benchmark'},'Unknown execution scope')
  if scope=='benchmark':
   ensure(self.lock.get('Gradle_benchmark_admitted') is True and self.out.is_relative_to(R/'jobs'),'Benchmark lacks admission')
   original=next(j for j in load(R/'manifest300.json') if j['sample_index_1based']==job['sample_index_1based'])
   for key in ['class_key','repo_id','focal_path','focal_class','seed','build_tool','module']:ensure(job[key]==original[key],'Benchmark job altered: '+key)
  else:
   ensure(self.lock.get('fixture_only') is True and self.out.is_relative_to(R/'validation'),'Qualification scope must be synthetic')
  ensure(job['build_tool']=='gradle' and not job.get('reused_result'),'Only new Gradle jobs')
  self.pins=dict(self.lock['code_and_input_hashes']);ensure(self.pins.get(str(Path(__file__).resolve()))==sha(__file__),'Controller not sealed')
  verify_pins(self.pins)
  self.tools=self.lock['tool_hashes'];verify_pins(self.tools)
  self.repo=self.out/'repo';self.build=self.repo/context['build_root_relative_to_repo'];self.module=self.repo/context['module_dir_relative_to_repo']
  self.env=environment();tmp=self.out/'temp';tmp.mkdir(exist_ok=False);self.env['TMP']=self.env['TEMP']=str(tmp)
  self.supervisor=GradleSupervisor(self.out,self.env,job,context,event=event)
  self.source_expected=source_hashes(self.repo);dump(self.out/'source_before.json',self.source_expected)
  for rel,h in self.source_expected.items():self.pins[str((self.repo/rel).resolve())]=h
  self.helpers=generation_bindings(None,self.out,event)
  self.cache_manifest=load(R/'cache_preparation_gradle_v1/recovery_v2/manifest.json')
  self.artifacts={}
  for home in [PRIVATE_HOME,Path('C:/Users/admin/.gradle')]:
   for r in self.cache_manifest:
    if r['relative'].startswith('caches/modules-2/files-2.1/'):
     self.artifacts[str((home/r['relative']).resolve())]=r['sha256']
  self.artifacts[str((WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar').resolve())]=sha(WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar')

 def run(self,stage,argv,cwd,timeout,init=None,extra=None):
  ensure(source_hashes(self.repo)==self.source_expected,'Source/native drift before stage')
  if (R/'STOP_REQUESTED.json').exists():raise GuardAbort('STOP; preserve evidence')
  ensure(shutil.disk_usage(R).free>=12_000_000_000,'Disk reserve reached')
  ticket={**self.lock,'schema':'B1_gradle_supervisor_v5','Gradle_execution_admitted':True,'supervisor_sha256':sha(R/'src/gradle_process_supervisor_v5.py'),'base_supervisor_sha256':sha(R/'src/process_supervisor_v1.py'),'command_policy_sha256':sha(R/'src/gradle_command_policy_v3.py'),'gradle_user_home':str(PRIVATE_HOME.resolve()),'gradle_launchers':{k:str(v) for k,v in launcher_paths().items()},'java_executable':str((JDK/'bin/java.exe').resolve()),'gradle_context_path':str(CONTEXT.resolve()),'gradle_context_sha256':sha(CONTEXT),'admitted_sample_indices':[self.job['sample_index_1based']],'code_and_input_hashes':dict(self.pins),'gradle_task_plans':{stage:{'argv_tail':argv[1:] if stage=='generation' else argv[8:] if init else argv[5:],'timeout_seconds':timeout}},'allowed_command_hashes':[command_hash(argv,cwd,timeout)],'init_script':None,'batch_admission_sha256':sha(self.admission)}
  if init:
   ticket['init_script']={'path':str(init.resolve()),'sha256':sha(init)};ticket['code_and_input_hashes'][str(init.resolve())]=sha(init)
   # Exact launcher head consists of5 elements plus2 init-script elements.
   ticket['gradle_task_plans'][stage]['argv_tail']=argv[7:]
  if extra:ticket.update(extra)
  number=len(list((self.out/'commands').glob('[0-9][0-9][0-9]')))+1
  path=self.out/'command_admissions'/f'{number:03d}.json';dump(path,ticket);self.supervisor.batch_admission=path
  self.event('STAGE',stage=stage)
  try:
   result=self.supervisor.run(argv,cwd,timeout,self.tools[str(Path(argv[0]).resolve())],{},stage=stage)
   return result,False
  except subprocess.TimeoutExpired as ex:
   return subprocess.CompletedProcess(argv,None,ex.stdout or '',ex.stderr or ''),True

 def gradle(self,stage,init,tasks):
  argv=[str(launcher_paths()[self.context['Gradle_version']]),'--offline','--no-daemon','-g',str(PRIVATE_HOME.resolve()),'--init-script',str(init.resolve()),*tasks]
  return self.run(stage,argv,self.build,900,init=init)

 def check_artifacts(self,audit):
  for rows in audit.values():
   for r in rows:
    p=Path(r['path']).resolve()
    if r['kind']=='file':
     h=sha(p);ensure(h==r['sha256'],'Resolved artifact hash differs')
     ensure(p.is_relative_to(self.repo) or self.artifacts.get(str(p))==h,'Resolved artifact outside frozen inventory')
     self.pins[str(p)]=h
    elif r['kind']=='directory':ensure(p.is_relative_to(self.repo),'External class/output directory')

 def generation(self,cp,attempt):
  ensure(attempt==self.generations+1 and attempt<=2,'Unexpected generation attempt order');self.generations=attempt
  module=self.module;job=self.job;rows=[]
  for value in cp.split(os.pathsep):
   p=Path(value).resolve()
   if p.is_dir():
    ensure(p.is_relative_to(self.repo),'Generation directory outside owned source')
    rows.append({'path':str(p),'kind':'directory','files':{q.relative_to(p).as_posix():sha(q) for q in p.rglob('*') if q.is_file()}})
   else:
    ensure(p.is_file() and (p.is_relative_to(self.repo) or self.artifacts.get(str(p))==sha(p)),'Unpinned generation artifact')
    self.pins[str(p)]=sha(p);rows.append({'path':str(p),'kind':'file','sha256':sha(p)})
  guard=self.out/'classpath_guards'/f'{attempt:02d}.json';dump(guard,rows);self.pins[str(guard.resolve())]=sha(guard)
  cp=os.pathsep.join(r['path'] for r in rows);focal=job['selected_test_fqcn'].removesuffix('_ESTest')
  raw=[str((JDK/'bin/java.exe').resolve()),'-jar',str(WORKSPACE/'scripts_v2/evosuite-1.2.0.jar'),'-class',focal,'-projectCP',cp,'-Dtest_dir='+str((module/'src/test/java').resolve()),'-Dreport_dir='+str((module/'evosuite-report').resolve()),*reviewer_options()]
  logical=checked_gradle_generation_argv(raw,job,self.out)
  transport=prepare_transport(logical,self.out,attempt,{'profile_seed_tools_validated':True,'logical_argv_sha256':argv_sha256(logical),'classpath_guard_path':str(guard.resolve()),'classpath_guard_sha256':sha(guard)})
  self.pins.update(transport['input_hashes'])
  retry=self.out/'generation_attempts/01/invocation.json' if attempt==2 else None
  if retry:self.pins[str(retry.resolve())]=sha(retry)
  details={'generation_attempt':attempt,'generation_classpath_guard':str(guard.resolve()),'generation_transport':load(transport['transport_manifest']) if transport['applied'] else None,'retry_evidence':str(retry.resolve()) if retry else None,'code_and_input_hashes':dict(self.pins)}
  result,timeout=self.run('generation',transport['argv'],module,240,extra=details)
  command=sorted((self.out/'commands').glob('[0-9][0-9][0-9]'))[-1];native=native_suite(module,job['selected_test_fqcn'])
  folder=self.out/'generation_attempts'/f'{attempt:02d}';folder.mkdir(parents=True,exist_ok=False);files=[]
  for row in native['files']:
   p=Path(row['path']);rel=p.relative_to(module);dest=folder/rel;dest.parent.mkdir(parents=True,exist_ok=True)
   with p.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst)
   ensure(sha(dest)==row['sha256'],'Native attempt archive mismatch');files.append({'path':rel.as_posix(),'sha256':sha(dest)})
   self.source_expected[p.relative_to(self.repo).as_posix()]=row['sha256'];self.pins[str(p.resolve())]=row['sha256']
  ensure(source_hashes(self.repo)==self.source_expected,'Generation changed source outside the exact native suite')
  dump(folder/'native_manifest.json',files)
  receipt={'attempt':attempt,'seed':job['seed'],'logical_argv':logical,'returncode':result.returncode,'timeout':timeout,'native_test_exists':native['test'] is not None,'native_complete':native['complete'],'stdout_path':str(command/'stdout.txt'),'stderr_path':str(command/'stderr.txt'),'stdout_sha256':sha(command/'stdout.txt'),'stderr_sha256':sha(command/'stderr.txt'),'native_manifest_sha256':sha(folder/'native_manifest.json'),'selection_rule':'primary success else one exact same-seed technical sanitizer retry before any measurement; no score selection'}
  dump(folder/'invocation.json',receipt);self.event('GENERATION_ATTEMPT',attempt=attempt,returncode=result.returncode,timeout=timeout,native_complete=native['complete'])
  return result,timeout,native,logical

def execute(out,job,context,admission,event):
 out=Path(out).resolve();commands=Commands(out,job,context,admission,event);module=commands.module
 ensure(not list(commands.repo.rglob('*.exec')),'Stale coverage execution input')
 version=context['Gradle_version'];plugin,engine=VERSIONS[version]
 jars=list((PRIVATE_HOME/'caches/modules-2/files-2.1/info.solidsoft.gradle.pitest/gradle-pitest-plugin'/plugin).glob('*/*.jar'));ensure(len(jars)==1,'Frozen PIT plugin missing/ambiguous')
 runtime=WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
 config={'Gradle_version':version,'repo_root':str(commands.repo),'build_root':context['build_root_relative_to_repo'],'module_selector':context['module_selector'],'focal_fqcn':job['selected_test_fqcn'].removesuffix('_ESTest'),'test_fqcn':job['selected_test_fqcn'],'runtime_jar':{'path':str(runtime),'sha256':sha(runtime)},'pit_plugin_classpath':[{'path':str(jars[0]),'sha256':sha(jars[0])}],'source_context_sha256':sha(CONTEXT),'add_junit4':False,'resolved_cp_audit':None}
 init,before_evidence=phase_recipe(config,out,'main_audit');prefix=context['task_prefix'];stage_records=[];generated=False;gate=False;measurement=False;evidence=out/'no_measurement_evidence';before=None
 result,timeout=commands.gradle('compile_classpath',init,[prefix+'classes',prefix+'b1WriteClasspaths']);stage_records.append({'stage':'compile_classpath','returncode':result.returncode,'timeout':timeout})
 if classify_environment_failure(result):raise GuardAbort('Offline/toolchain environment unavailable; retain unscored, do not repair or zero-fill')
 if result.returncode==0 and not timeout:
  before=load(before_evidence/'b1_compile_audit.json');commands.check_artifacts(before)
  rawcp=[r['path'] for r in before['main_runtime']];parts,skipped=commands.helpers['evosuite_classpath_entries'](rawcp)
  dump(out/'generation_classpath_rule.json',{'input':'ordered sourceSets.main.runtimeClasspath before runtime/JUnit/PIT integration','ordered_raw':rawcp,'ordered_valid':parts,'skipped':skipped,'helper':'unchanged E49 evosuite_classpath_entries','test_compile_not_added':True})
  ensure(parts,'No resolved production classpath; no generation admitted')
  cp=os.pathsep.join(parts);result,timeout,native,logical=commands.generation(cp,1)
  if not timeout and (result.returncode!=0 or native['test'] is None):
   sanitized,removed=commands.helpers['sanitize_evosuite_generation_classpath'](parts)
   if sanitized and sanitized!=parts and commands.helpers['should_retry_evosuite_with_sanitized_classpath']((result.stdout or '')+'\n'+(result.stderr or '')):
    if native['test'] is not None:
     p=native['test'];dest=out/'generation_attempts/01/primary_before_technical_retry.java';ensure(p.resolve().is_relative_to(out/'repo') and dest.resolve().is_relative_to(out),'Retry quarantine escapes job');p.rename(dest)
     del commands.source_expected[p.relative_to(commands.repo).as_posix()];commands.pins.pop(str(p.resolve()),None)
    event('TECHNICAL_RETRY',same_seed=True,removed_classpath_entries=removed,basis='predeclared exact marker; before measurement')
    result,timeout,native,logical=commands.generation(os.pathsep.join(sanitized),2)
  generated=not timeout and result.returncode==0 and native['test'] is not None
  dump(out/'native_generated.json',json.loads(json.dumps(native,default=str)))
  if generated and native['complete']:
   junit=[]
   for r in before['test_compile']:
    match=re.fullmatch(r'junit-([0-9][A-Za-z0-9_.-]*)\.jar',Path(r['path']).name)
    if match:junit.append(match.group(1))
   ensure(all(v.startswith('4.') for v in junit) and len(set(junit))<=1,'Existing non-JUnit4/ambiguous runtime; no upgrade or dependency repair')
   config['add_junit4']=not bool(junit)
   if not junit:config['resolved_cp_audit']={'status':'PASS_RESOLVED_CP_AUDIT','junit4_missing':True,'evidence_sha256':sha(before_evidence/'b1_compile_audit.json')}
   init,evidence=phase_recipe(config,out,'measure');result,timeout=commands.gradle('classpath',init,[prefix+'b1WriteClasspaths'])
   stage_records.append({'stage':'classpath','returncode':result.returncode,'timeout':timeout})
   ensure(result.returncode==0 and not timeout,'Measurement dependency audit unavailable; do not score or repair')
   after=load(evidence/'b1_measurement_dependency_audit.json');commands.check_artifacts(after)
   signature=lambda rows:[(r['path'],r.get('sha256'),r['kind']) for r in rows]
   ensure(all(signature(before[k])==signature(after[k]) for k in ['main_compile','main_runtime']),'Production dependency closure changed')
   old={r['path']:r.get('sha256') for r in before['test_compile']};new={r['path']:r.get('sha256') for r in after['test_compile']};ensure(all(new.get(k)==v for k,v in old.items()),'Existing test dependency removed/upgraded')
   ensure(any(Path(r['path']).name=='pitest-command-line-'+engine+'.jar' for r in after['pit_engine']),'Wrong effective PIT engine')
   measurement=True;result,timeout=commands.gradle('test_jacoco',init,[prefix+'b1NativeTest',prefix+'b1NativeJacocoReport']);stage_records.append({'stage':'test_jacoco','returncode':result.returncode,'timeout':timeout})
   if result.returncode==0 and not timeout:
    result,timeout=commands.gradle('pit',init,[prefix+'pitest']);stage_records.append({'stage':'pit','returncode':result.returncode,'timeout':timeout})
    gate=not timeout # Preserve historical Gradle gate: nonzero PIT rc alone does not erase test+JaCoCo success.
 ensure(source_hashes(commands.repo)==commands.source_expected,'Source/native changed during measurement')
 if before is not None:
  for r in load(before_evidence/'b1_production_classes.json').items():
   root,rel=r[0].split('::',1);p=Path(root)/rel;ensure(p.is_file() and sha(p)==r[1],'Production bytecode changed/missing')
 for manifest in (out/'generation_attempts').glob('*/native_manifest.json'):
  for row in load(manifest):ensure(sha(manifest.parent/row['path'])==row['sha256'],'Generation attempt archive drift')
 raw=parse(module,evidence,job,gate)
 result={'sample_index_1based':job['sample_index_1based'],'class_key':job['class_key'],'repo_id':job['repo_id'],'seed':job['seed'],'configuration':'E1_Gradle_native_v1_CANDIDATE_REQUIRES_ADMISSION','batch_admission_sha256':sha(admission),'Gradle_version':version,'generation_success':generated,'generation_calls':commands.generations,'measurement_attempted':measurement,'native_junit_added':config['add_junit4'],'stage_outcomes':stage_records,'GPT_API_calls':0,'source_guard':'PASS','production_bytecode_guard':'PASS','terminal':True,**raw}
 dump(out/'result.json',result);event('JOB_TERMINAL',result_sha256=sha(out/'result.json'),gate=int(gate));archive(out);return result

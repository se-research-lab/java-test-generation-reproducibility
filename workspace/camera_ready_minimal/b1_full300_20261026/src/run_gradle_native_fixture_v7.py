"""Prepared synthetic measurement qualification; explicit version, idle mutex.
Reuses a saved synthetic native suite. No EvoSuite/GPT generation or benchmark.
"""
import argparse,csv,json,msvcrt,os,re,shutil,sys,traceback
from parallel_pin_verify_v1 import verify_pins
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from maven_adapter_v1 import R,JDK,sha,dump,GuardAbort
from gradle_command_policy_v3 import PRIVATE_HOME,CONTEXT,launcher_paths,command_hash,ensure
from gradle_process_supervisor_v5 import GradleSupervisor,environment
from gradle_native_recipe_v7 import write_recipe,VERSIONS,groovy
from maven_controller_v2 import source_hashes,archive
from measurement_parser_v1 import inventory_module
from run_maven_b1_v3 import guards
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
CACHE=R/'cache_preparation_gradle_v1';COMPLETE=CACHE/'recovery_v2/complete.json';CACHE_MANIFEST=CACHE/'recovery_v2/manifest.json'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def exclusive_copy(source,dest,expected):
 ensure(sha(source)==expected,'Saved fixture input changed');dest.parent.mkdir(parents=True,exist_ok=True)
 with source.open('rb') as f,dest.open('xb') as t:shutil.copyfileobj(f,t)
 ensure(sha(dest)==expected,'Fixture copy differs')
def main_bytecode(module):
 roots=[p for p in [module/'build/classes/main',module/'build/classes/java/main'] if p.is_dir()]
 ensure(len(roots)==1,'Expected one wrapper-specific main class output')
 result={p.relative_to(roots[0]).as_posix():sha(p) for p in roots[0].rglob('*.class')};ensure(result,'Main fixture not compiled');return result
def cp_signature(rows):return [(r['path'],r.get('sha256'),r['kind']) for r in rows]
def junit4_present(rows):
 versions=[]
 for r in rows:
  name=r['path'].replace('\\','/').rsplit('/',1)[-1]
  match=re.fullmatch(r'junit-([0-9][A-Za-z0-9_.-]*)\.jar',name)
  if match:versions.append(match.group(1))
 ensure(all(v.startswith('4.') for v in versions),'Existing non-JUnit4 requires separate review; do not upgrade')
 ensure(len(set(versions))<=1,'Ambiguous JUnit versions in fixture test classpath')
 return bool(versions)
def verify_rows(rows,home):
 records={str((home/r['relative']).resolve()):r['sha256'] for r in rows}
 ensure(len(records)==len(rows),'Duplicate cache input paths')
 verify_pins(records)
def execute_fixture(version):
 out=R/'validation/gradle_native_runtime_fixture_v7'/('gradle_'+version)
 ensure(not out.exists(),'No overwrite or implicit qualification retry')
 guards(load(R/'admission_maven_v3.json'))
 ensure(load(R/'validation/gradle_versions_qualification_v1/complete.json')['status']=='PASS_VERSION_COMMANDS_ONLY','Launcher qualification missing')
 pure=load(R/'validation/gradle_native_recipe_v7/result.json');ensure(pure['status']=='PASS_PURE_VALIDATION' and pure['source_sha256']==sha(R/'src/gradle_native_recipe_v7.py'),'Recipe source drift')
 completion=load(COMPLETE);ensure(completion['status']=='PASS_PRIVATE_CACHE_PREPARATION_ONLY' and completion['manifest_sha256']==sha(CACHE_MANIFEST),'Private cache not verified')
 cache_rows=load(CACHE_MANIFEST)
 immutable=[r for r in cache_rows if r['relative'].startswith(('wrapper/dists/','caches/modules-2/files-2.1/'))]
 verify_rows(immutable,PRIVATE_HOME)
 original_cache=Path(load(CACHE/'protocol.json')['source']);ensure(original_cache==Path('C:/Users/admin/.gradle'),'Unexpected original Gradle cache root');verify_rows(cache_rows,original_cache)
 contexts=load(CONTEXT);context=next(c for c in contexts if c['Gradle_version']==version)
 job=next(j for j in load(R/'manifest300.json') if j['sample_index_1based']==context['sample_index_1based'])
 # The real row is used ONLY to bind wrapper/build-root/module grammar. No real
 # focal source/test is copied and no benchmark result is emitted for that row.
 out.mkdir(parents=True,exist_ok=False);repo=out/'repo';build=repo/context['build_root_relative_to_repo'];module=repo/context['module_dir_relative_to_repo']
 build.mkdir(parents=True,exist_ok=True);module.mkdir(parents=True,exist_ok=True)
 saved=R/'validation/long_classpath_fixture_v1';index={r['relative']:r for r in load(saved/'artifact_manifest.json')};inputs=[]
 for rel in ['src/main/java/fixture/BranchFixture.java','src/test/java/fixture/BranchFixture_ESTest.java','src/test/java/fixture/BranchFixture_ESTest_scaffolding.java']:
  source=saved/'repo'/rel;dest=module/rel;record=index['repo/'+rel];exclusive_copy(source,dest,record['sha256']);inputs.append({'saved_source':str(source),'copied_fixture':str(dest),'sha256':record['sha256']})
 testng_fixture=version in {'5.2.1','6.9.4'}
 maven_cache=R/'cache_preparation_v1/maven_cache';maven_manifest=B/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json'
 maven_hashes={r['relative']:r['sha256'] for r in load(maven_manifest)}
 junit=maven_cache/'junit/junit/4.13.2/junit-4.13.2.jar';hamcrest=maven_cache/'org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
 for p in [junit,hamcrest]:ensure(maven_hashes[p.relative_to(maven_cache).as_posix()]==sha(p),'Pinned fixture test dependency drift')
 deps=[]
 if testng_fixture:
  testng=list((PRIVATE_HOME/'caches/modules-2/files-2.1/org.testng/testng/6.8.21').glob('*/*.jar'));ensure(len(testng)==1,'Synthetic TestNG dependency missing');deps=testng
 else:deps=[junit,hamcrest]
 config_name='testCompile' if version=='2.13' else 'testImplementation'
 body="buildscript { repositories { mavenCentral() } }\napply plugin: 'java'\nsourceCompatibility = '1.8'\ntargetCompatibility = '1.8'\nrepositories { mavenCentral() }\ndependencies { "+config_name+' files('+', '.join(groovy(str(p)) for p in deps)+') }\n'
 if testng_fixture:body+="test { useTestNG() }\n"
 (module/'build.gradle').write_text(body,encoding='utf-8')
 settings="rootProject.name = 'b1-native-synthetic-fixture'\n"
 if context['module_selector']!='.':
  settings+='include '+groovy(':'+context['module_selector'].replace('/',':'))+'\n'
  if build!=module:(build/'build.gradle').write_text('buildscript { repositories { mavenCentral() } }\n// Synthetic root; selected module owns Java/PIT tasks.\n',encoding='utf-8')
 (build/'settings.gradle').write_text(settings,encoding='utf-8')
 plugin_version,engine=VERSIONS[version];plugins=list((PRIVATE_HOME/'caches/modules-2/files-2.1/info.solidsoft.gradle.pitest/gradle-pitest-plugin'/plugin_version).glob('*/*.jar'));ensure(len(plugins)==1,'Pinned PIT plugin missing')
 runtime=R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
 config={'Gradle_version':version,'repo_root':str(repo),'build_root':context['build_root_relative_to_repo'],'module_selector':context['module_selector'],'focal_fqcn':'fixture.BranchFixture','test_fqcn':'fixture.BranchFixture_ESTest','runtime_jar':{'path':str(runtime),'sha256':sha(runtime)},'pit_plugin_classpath':[{'path':str(plugins[0]),'sha256':sha(plugins[0])}],'source_context_sha256':sha(CONTEXT),'add_junit4':False,'resolved_cp_audit':None}
 first=out/'recipe_before';write_recipe(config,first)
 before_sources=source_hashes(repo);dump(out/'source_before.json',before_sources);dump(out/'fixture_inputs.json',inputs)
 pinpaths=[Path(__file__),R/'src/parallel_pin_verify_v1.py',R/'src/gradle_generation_plan_guard_v1.py',R/'src/gradle_generation_argv_v1.py',JDK/'lib/tools.jar',R/'src/gradle_native_recipe_v7.py',R/'src/gradle_command_policy_v3.py',R/'src/gradle_process_supervisor_v5.py',R/'src/process_supervisor_v1.py',R/'src/maven_adapter_v1.py',R/'src/maven_controller_v2.py',R/'src/measurement_parser_v1.py',COMPLETE,CACHE_MANIFEST,CONTEXT,runtime,plugins[0],junit,hamcrest,maven_manifest,saved/'artifact_manifest.json',saved/'validation_result.json']
 pinpaths += [repo/p for p in before_sources]+[Path(r['saved_source']) for r in inputs]+deps
 pins={str(p.resolve()):sha(p) for p in pinpaths}
 for r in immutable:pins[str((PRIVATE_HOME/r['relative']).resolve())]=r['sha256']
 for r in immutable:
  if r['relative'].startswith('caches/modules-2/files-2.1/'):
   pins[str((original_cache/r['relative']).resolve())]=r['sha256']
 launchers=launcher_paths();tools={str(p.resolve()):sha(p) for p in [JDK/'bin/java.exe',*launchers.values()]}
 dump(out/'protocol.json',{'scope':'synthetic native measurement only; NOT a Gradle benchmark or generation qualification','wrapper_metadata_context_only':{'sample_index_1based':job['sample_index_1based'],'class_key':job['class_key']},'actual_fixture_class':'fixture.BranchFixture','saved_native_suite':str(saved),'Gradle_version':version,'synthetic_original_test_framework':'TestNG6.8.21' if testng_fixture else 'JUnit4.13.2','engine_candidate':engine,'agent_candidate':'0.8.6','input_pins':pins,'new_benchmark_classes':0,'new_EvoSuite_calls':0,'GPT_API_calls':0})
 def event(kind,**kw):
  with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kw})+'\n')
  audit.log('B1_GRADLE_NATIVE_FIXTURE_'+kind,Gradle_version=version,**kw)
 supervisor=None;stage_count=0
 def run_stage(stage,init,tasks):
  nonlocal supervisor,stage_count
  stage_count+=1;argv=[str(launchers[version]),'--offline','--no-daemon','-g',str(PRIVATE_HOME.resolve()),'--init-script',str(init.resolve()),*tasks]
  command_pins={**pins,str(init.resolve()):sha(init)}
  admission={'schema':'B1_gradle_supervisor_v5','Gradle_execution_admitted':True,'execution_scope':'runtime_qualification','Gradle_runtime_qualified':False,'Gradle_benchmark_admitted':False,'GPT_generation_authorized':False,'supervisor_sha256':sha(R/'src/gradle_process_supervisor_v5.py'),'base_supervisor_sha256':sha(R/'src/process_supervisor_v1.py'),'command_policy_sha256':sha(R/'src/gradle_command_policy_v3.py'),'gradle_user_home':str(PRIVATE_HOME.resolve()),'gradle_launchers':{k:str(v) for k,v in launchers.items()},'java_executable':str((JDK/'bin/java.exe').resolve()),'tool_hashes':tools,'gradle_context_path':str(CONTEXT.resolve()),'gradle_context_sha256':sha(CONTEXT),'admitted_sample_indices':[job['sample_index_1based']],'code_and_input_hashes':command_pins,'gradle_task_plans':{stage:{'argv_tail':tasks,'timeout_seconds':900}},'allowed_command_hashes':[command_hash(argv,build,900)],'init_script':{'path':str(init.resolve()),'sha256':sha(init)},'fixture_only':True,'real_benchmark_row_executed':False,'new_EvoSuite_calls':0}
  path=out/'command_admissions'/f'{stage_count:03d}.json';dump(path,admission)
  if supervisor is None:
   env=environment();tmp=out/'temp';tmp.mkdir();env['TMP']=env['TEMP']=str(tmp);supervisor=GradleSupervisor(out,env,job,context,path,event)
  else:supervisor.batch_admission=path
  result=supervisor.run(argv,build,900,tools[str(launchers[version])],{},stage=stage)
  ensure(result.returncode==0,'Qualification stage failed: '+stage)
  ensure(source_hashes(repo)==before_sources,'Fixture source/native suite changed')
  return result
 try:
  prefix=context['task_prefix'];run_stage('compile_classpath',first/'main_audit/init.gradle',[prefix+'classes',prefix+'b1WriteClasspaths'])
  baseline=main_bytecode(module);dump(out/'main_bytecode_before.json',baseline)
  before=load(first/'main_audit/evidence/b1_compile_audit.json');junit_present=junit4_present(before['test_compile'])
  config['add_junit4']=not junit_present
  if not junit_present:config['resolved_cp_audit']={'status':'PASS_RESOLVED_CP_AUDIT','junit4_missing':True,'evidence_sha256':sha(first/'main_audit/evidence/b1_compile_audit.json')}
  second=out/'recipe_measure';write_recipe(config,second);init=second/'measure/init.gradle';evidence=second/'measure/evidence'
  run_stage('classpath',init,[prefix+'b1WriteClasspaths']);after=load(evidence/'b1_measurement_dependency_audit.json')
  ensure(cp_signature(before['main_compile'])==cp_signature(after['main_compile']),'Main compile closure changed by test integration')
  ensure(cp_signature(before['main_runtime'])==cp_signature(after['main_runtime']),'Main runtime closure changed by test integration')
  initial={r['path']:r.get('sha256') for r in before['test_compile']}
  observed={r['path']:r.get('sha256') for r in after['test_compile']}
  ensure(all(observed.get(p)==h for p,h in initial.items()),'Existing test dependency removed or upgraded')
  artifacts={str((PRIVATE_HOME/r['relative']).resolve()):r['sha256'] for r in immutable}
  artifacts.update({str((original_cache/r['relative']).resolve()):r['sha256'] for r in immutable if r['relative'].startswith('caches/modules-2/files-2.1/')})
  artifacts.update({str(p.resolve()):sha(p) for p in [runtime,junit,hamcrest,*deps]})
  for rows in after.values():
   for r in rows:
    if r['kind']=='file':ensure(artifacts.get(str(Path(r['path']).resolve()))==r['sha256'],'Resolved tool/dependency not in frozen artifact inventory')
  engine_jars=[Path(r['path']).name for r in after['pit_engine'] if re.fullmatch(r'pitest(-entry|-command-line)?-[0-9.]+\.jar',Path(r['path']).name)]
  ensure(any(name=='pitest-command-line-'+engine+'.jar' for name in engine_jars),'Effective PIT engine not the locked candidate')
  run_stage('test_jacoco',init,[prefix+'b1NativeTest',prefix+'b1NativeJacocoReport']);run_stage('pit',init,[prefix+'pitest'])
  ensure(main_bytecode(module)==baseline,'Main production bytecode changed during measurement')
  inventory=inventory_module();native=(module/'src/test/java/fixture/BranchFixture_ESTest.java').read_text(encoding='utf-8');methods=inventory.inventory_java_tests(native)['methods'];cases=[]
  suites=list((evidence/'surefire-native').glob('TEST-*.xml'));ensure(len(suites)==1,'Unexpected suite count')
  suite=ET.parse(suites[0]).getroot();ensure(suite.get('name')=='fixture.BranchFixture_ESTest','Foreign suite')
  for case in suite.findall('testcase'):
   ensure(case.get('classname')=='fixture.BranchFixture_ESTest' and not list(case.findall('failure')+case.findall('error')+case.findall('skipped')),'Failed/skipped/foreign testcase')
   cases.append(inventory.normalize_case(case.get('name'),'fixture.BranchFixture_ESTest'))
  ensure(Counter(cases)==Counter(methods) and bool(cases),'Native methods did not execute exactly once')
  with (evidence/'jacoco-native.csv').open(encoding='utf-8-sig',newline='') as f:jac=[r for r in csv.DictReader(f) if r.get('CLASS')=='BranchFixture' and r.get('PACKAGE','').replace('/','.')=='fixture']
  ensure(jac and any(int(r['INSTRUCTION_COVERED'])>0 for r in jac),'Fresh focal JaCoCo evidence missing')
  reports=list((evidence/'pit-native').rglob('mutations.csv'));ensure(len(reports)==1,'PIT report missing/ambiguous')
  with reports[0].open(encoding='utf-8-sig',newline='') as f:mutants=[r for r in csv.reader(f) if len(r)==7 and r[0]=='BranchFixture.java' and r[1]=='fixture.BranchFixture']
  killed=[r for r in mutants if r[5]=='KILLED'];ensure(mutants and killed and all('fixture.BranchFixture_ESTest' in r[6] for r in killed),'Positive-control mutation/provider evidence missing')
  verify_rows(immutable,PRIVATE_HOME);verify_rows(cache_rows,original_cache);guards(load(R/'admission_maven_v3.json'))
  result={'status':'PASS_SYNTHETIC_NATIVE_MEASUREMENT_ONLY','Gradle_version':version,'engine_version_from_resolved_JARs':engine_jars,'testcases':len(cases),'focal_mutants':len(mutants),'killed_mutants':len(killed),'main_compile_runtime_closure_unchanged':True,'main_bytecode_unchanged':True,'source_native_unchanged':True,'original_source_cache_bytes_unchanged':True,'legacy_absolute_artifact_paths':True,'JDK8_tools_bootstrap':'exact E49/Maven setting','absent_native_runtime_paths':'excluded lazily only if nonexistent','cache_write_home':'private -g only; source artifacts immutable pinned reads','JUnit_added_after_resolved_audit':config['add_junit4'],'original_test_framework':('TestNG' if testng_fixture else 'JUnit'),'native_provider':'JUnit4','legacy_exact_focal_target':True,'new_EvoSuite_calls':0,'GPT_API_calls':0,'new_benchmark_classes':0,'EvoSuite_Gradle_generation_qualified':False,'Gradle_benchmark_admitted':False}
  dump(out/'result.json',result);event('VALIDATED',result_sha256=sha(out/'result.json'));archive(out);print(json.dumps(result,indent=2))
 except BaseException as ex:
  dump(out/'failure.json',{'status':'QUALIFICATION_FAILED_NO_BENCHMARK','stage_commands':stage_count,'error_type':type(ex).__name__,'detail':str(ex),'traceback':traceback.format_exc(),'automatic_retry':False,'new_EvoSuite_calls':0,'GPT_API_calls':0});event('FAILED',error_type=type(ex).__name__,detail=str(ex));archive(out);raise

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--version',choices=sorted(VERSIONS),required=True);parser.add_argument('--check-idle-only',action='store_true');args=parser.parse_args()
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  try:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:print('NOT_STARTED: Maven dispatcher busy; no fixture output or process created');return 2
  try:
   if args.check_idle_only:print('IDLE_CHECK_ONLY: lock available; no fixture files or process created');return 0
   execute_fixture(args.version);return 0
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':sys.exit(main())

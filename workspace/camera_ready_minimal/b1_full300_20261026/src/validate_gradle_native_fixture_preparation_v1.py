"""Pure guard/grammar validation; never calls the fixture or any process."""
import ast,json,sys
from pathlib import Path
from maven_adapter_v1 import R,JDK,sha,dump,GuardAbort
from run_gradle_native_fixture_v1 import junit4_present
from gradle_command_policy_v2 import GradleCommandPolicy,PRIVATE_HOME,CONTEXT,launcher_paths
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
out=R/'validation/gradle_native_fixture_preparation_v1';out.mkdir(exist_ok=False);checks=[]
source=R/'src/run_gradle_native_fixture_v1.py';ast.parse(source.read_text(encoding='utf-8'))
for value in ['D:/cache/junit/junit/4.13.2/hash/junit-4.13.2.jar',r'D:\cache\junit-4.11.jar']:
 assert junit4_present([{'path':value}]);checks.append('JUnit4 detected from '+value)
for value in ['D:/cache/junit-jupiter-api-5.10.0.jar','D:/cache/testng-6.8.21.jar']:
 assert not junit4_present([{'path':value}]);checks.append('Other framework does not count as native JUnit4')
for rows in [[{'path':'D:/cache/junit-3.8.1.jar'}],[{'path':'D:/cache/junit-4.11.jar'},{'path':'D:/cache/junit-4.13.2.jar'}]]:
 try:junit4_present(rows)
 except GuardAbort:checks.append('Old/ambiguous JUnit rejected without upgrade')
 else:raise AssertionError('Unsafe JUnit classification')
contexts=load(CONTEXT);jobs={j['sample_index_1based']:j for j in load(R/'manifest300.json')};launchers=launcher_paths();plans=[]
tools={str(p.resolve()):sha(p) for p in [JDK/'bin/java.exe',*launchers.values()]}
for version in ['2.13','5.2.1','6.9.4','8.14.4']:
 context=next(c for c in contexts if c['Gradle_version']==version);job=jobs[context['sample_index_1based']];folder=out/('gradle_'+version)
 build=folder/'repo'/context['build_root_relative_to_repo'];module=folder/'repo'/context['module_dir_relative_to_repo'];build.mkdir(parents=True);module.mkdir(parents=True,exist_ok=True)
 init=folder/'static_only.gradle';init.write_text('// STATIC GRAMMAR CHECK ONLY; no execution admission.\n',encoding='utf-8')
 prefix=context['task_prefix']
 for stage,tasks in [('compile_classpath',[prefix+'classes',prefix+'b1WriteClasspaths']),('classpath',[prefix+'b1WriteClasspaths']),('test_jacoco',[prefix+'b1NativeTest',prefix+'b1NativeJacocoReport']),('pit',[prefix+'pitest'])]:
  lock={'Gradle_execution_admitted':False,'execution_scope':'runtime_qualification','gradle_user_home':str(PRIVATE_HOME.resolve()),'gradle_launchers':{k:str(v) for k,v in launchers.items()},'java_executable':str((JDK/'bin/java.exe').resolve()),'tool_hashes':tools,'gradle_context_path':str(CONTEXT.resolve()),'gradle_context_sha256':sha(CONTEXT),'admitted_sample_indices':[job['sample_index_1based']],'code_and_input_hashes':{str(init.resolve()):sha(init)},'init_script':{'path':str(init.resolve()),'sha256':sha(init)},'gradle_task_plans':{stage:{'argv_tail':tasks,'timeout_seconds':900}}}
  policy=GradleCommandPolicy(folder,job,context,lock);argv=[str(launchers[version]),'--offline','--no-daemon','-g',str(PRIVATE_HOME.resolve()),'--init-script',str(init.resolve()),*tasks]
  assert policy.validate(argv,build,900,stage)==(argv,build.resolve())
  plans.append({'version':version,'stage':stage,'tasks':tasks,'timeout':900,'grammar':'PASS','execution_admitted':False})
checks.append('All16 wrapper/stage command plans match the owned offline grammar without execution authority')
assert not (R/'validation/gradle_native_runtime_fixture_v1').exists(),'Runtime fixture must remain unstarted'
result={'status':'PASS_PREPARATION_ONLY','source_sha256':sha(source),'recipe_v4_sha256':sha(R/'src/gradle_native_recipe_v4.py'),'checks':checks,'plans':plans,'processes_started':0,'Java_Gradle_EvoSuite_calls':0,'GPT_API_calls':0,'runtime_qualified':False,'Gradle_benchmark_admitted':False}
dump(out/'result.json',result);audit.log('B1_GRADLE_NATIVE_FIXTURE_PREPARATION_VALIDATED',result_sha256=sha(out/'result.json'),source_sha256=sha(source),processes_started=0,GPT_API_calls=0)
print(json.dumps({'status':result['status'],'command_plans':len(plans),'checks':len(checks),'processes_started':0,'runtime_qualified':False},indent=2))

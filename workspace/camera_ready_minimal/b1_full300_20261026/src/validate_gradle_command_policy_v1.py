"""Pure guard validation only. No admission and no process launch of any kind."""
import copy,json,sys
from pathlib import Path
from gradle_command_policy_v1 import R,JDK,CONTEXT,PRIVATE_HOME,launcher_paths,GradleCommandPolicy,command_hash,tool_paths
from gradle_process_supervisor_v1 import GradleSupervisor
from process_supervisor_v1 import Supervisor
from maven_adapter_v1 import GuardAbort,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'validation/gradle_command_policy_v1';O.mkdir(parents=True,exist_ok=False);checks=[]
rows=json.loads(CONTEXT.read_text(encoding='utf-8'));manifest=json.loads((R/'manifest300.json').read_text(encoding='utf-8'));jobs={j['sample_index_1based']:j for j in manifest}
def reject(name,fn):
 try:fn()
 except GuardAbort:checks.append(name)
 else:raise AssertionError('Accepted unsafe case: '+name)
def fixture(row,name):
 out=O/name;root=out/'repo'/row['build_root_relative_to_repo'];root.mkdir(parents=True)
 launch=launcher_paths();java=(JDK/'bin/java.exe').resolve();lock={'gradle_user_home':str(PRIVATE_HOME.resolve()),'gradle_launchers':{k:str(v) for k,v in launch.items()},'java_executable':str(java),'tool_hashes':{str(p):'0'*64 for p in list(launch.values())+[java]},'gradle_context_path':str(CONTEXT.resolve()),'gradle_context_sha256':sha(CONTEXT),'admitted_sample_indices':[row['sample_index_1based']],'execution_scope':'runtime_qualification','Gradle_execution_admitted':False,'Gradle_runtime_qualified':False,'GPT_generation_authorized':False,'code_and_input_hashes':{},'gradle_task_plans':{'version':{'argv_tail':['--version'],'timeout_seconds':30},'java_version':{'argv_tail':['-version'],'timeout_seconds':15},'compile_classpath':{'argv_tail':[row['task_prefix']+'classes',row['task_prefix']+'b1WriteClasspaths'],'timeout_seconds':900},'test_jacoco':{'argv_tail':[row['task_prefix']+'b1NativeTest',row['task_prefix']+'b1NativeJacocoReport'],'timeout_seconds':900},'pit':{'argv_tail':[row['task_prefix']+'pitest'],'timeout_seconds':900}}}
 policy=GradleCommandPolicy(out,jobs[row['sample_index_1based']],row,lock)
 head=[str(launch[row['Gradle_version']]),'--offline','--no-daemon','-g',str(PRIVATE_HOME.resolve())]
 return out,root,lock,policy,head
contexts=[]
for row in rows:
 out,root,lock,policy,head=fixture(row,f"sample{row['sample_index_1based']:03d}")
 for stage in ['compile_classpath','test_jacoco','pit']:
  args=head+lock['gradle_task_plans'][stage]['argv_tail'];assert policy.validate(args,root,900,stage)[0]==args
 contexts.append({'sample_index_1based':row['sample_index_1based'],'Gradle_version':row['Gradle_version'],'task_prefix':row['task_prefix'],'build_root':row['build_root_relative_to_repo']})
checks.append('all40 exact metadata cwd/version/module/task plans accepted without execution')
row=rows[0];out,root,lock,policy,head=fixture(row,'negative_cases');good=head+lock['gradle_task_plans']['pit']['argv_tail']
reject('missing offline rejected',lambda:policy.validate([a for a in good if a!='--offline'],root,900,'pit'))
reject('daemon option rejected',lambda:policy.validate([a for a in good if a!='--no-daemon'],root,900,'pit'))
reject('shared Gradle home rejected',lambda:policy.validate([*good[:4],str(Path.home()/'.gradle'),*good[5:]],root,900,'pit'))
reject('wrong cwd rejected',lambda:policy.validate(good,out,900,'pit'))
reject('unbounded/changed stage timeout rejected',lambda:policy.validate(good,root,901,'pit'))
reject('implicit Maven300 timeout rejected',lambda:policy.validate(good,root,300,'pit'))
reject('unknown stage rejected',lambda:policy.validate(good,root,900,'undeclared'))
reject('extra refresh/network flag rejected',lambda:policy.validate(good+['--refresh-dependencies'],root,900,'pit'))
reject('project dir override rejected',lambda:policy.validate(good+['--project-dir',str(out)],root,900,'pit'))
reject('wrong module task rejected',lambda:policy.validate(head+[':foreign:pitest'],root,900,'pit'))
bad=copy.deepcopy(lock);bad['gradle_task_plans']['pit']['argv_tail']=[':foreign:pitest'];badpolicy=GradleCommandPolicy(out,jobs[row['sample_index_1based']],row,bad)
reject('admission cannot extend module prefix',lambda:badpolicy.validate(head+[':foreign:pitest'],root,900,'pit'))
bad=copy.deepcopy(lock);bad['gradle_launchers']['2.13']=str(PRIVATE_HOME/'wrapper/dists/gradle-2.13-all/foreign/gradle-2.13/bin/gradle.bat')
reject('admission cannot extend launcher hash slot',lambda:tool_paths(bad))
bad=copy.deepcopy(lock);bad['java_executable']=str(Path(sys.executable).resolve());bad['tool_hashes'][str(Path(sys.executable).resolve())]='0'*64
reject('arbitrary hashed tool rejected',lambda:tool_paths(bad))
java=[str((JDK/'bin/java.exe').resolve()),'-version'];assert policy.validate(java,root,15,'java_version')[0]==java;checks.append('qualification Java sanity allowed at15s only')
reject('Java EvoSuite generation remains unwired and rejected',lambda:policy.validate([java[0],'-jar','evosuite.jar'],root,240,'java_version'))
bad=copy.deepcopy(lock);bad['execution_scope']='benchmark';p=GradleCommandPolicy(out,jobs[row['sample_index_1based']],row,bad)
reject('benchmark --version rejected',lambda:p.validate(head+['--version'],root,30,'version'))
init=out/'native.gradle';init.write_text('// pure fixture only\n',encoding='utf-8');lock['init_script']={'path':str(init.resolve()),'sha256':sha(init)};lock['code_and_input_hashes'][str(init.resolve())]=sha(init)
p=GradleCommandPolicy(out,jobs[row['sample_index_1based']],row,lock);argv=head+['--init-script',str(init.resolve())]+lock['gradle_task_plans']['pit']['argv_tail'];assert p.validate(argv,root,900,'pit')[0]==argv;checks.append('owned pinned init script accepted')
reject('unplanned global init script rejected',lambda:p.validate(head+['--init-script',str(Path.home()/'.gradle/init.gradle')]+lock['gradle_task_plans']['pit']['argv_tail'],root,900,'pit'))
bad=copy.deepcopy(lock);bad['init_script']['sha256']='0'*64;bad['code_and_input_hashes'][str(init.resolve())]='0'*64;pbad=GradleCommandPolicy(out,jobs[row['sample_index_1based']],row,bad)
reject('init hash drift rejected',lambda:pbad.validate(argv,root,900,'pit'))
assert GradleSupervisor.kill_owned is Supervisor.kill_owned;checks.append('owned PID/starttime tree termination inherited unchanged')
env={'JAVA_HOME':str(JDK),'GRADLE_USER_HOME':str(PRIVATE_HOME.resolve())}
supervisor=GradleSupervisor(out,env,jobs[row['sample_index_1based']],row)
reject('supervisor without admission cannot spawn',lambda:supervisor.run(good,root,900,'0'*64,{},stage='pit'))
assert not list(supervisor.command_root.iterdir());checks.append('no command record/spawn before missing admission rejection')
assert command_hash(good,root,900)!=command_hash(good,root,300);checks.append('command hash binds timeout')
report={'status':'PASS_STATIC_ONLY','qualification':'NOT_RUNTIME_QUALIFIED','benchmark_admitted':False,'checks':checks,'metadata_contexts_validated':contexts,'processes_started':0,'Java_calls':0,'Gradle_calls':0,'EvoSuite_calls':0,'GPT_API_calls':0,'code_hashes':{str(p):sha(p) for p in [R/'src/gradle_command_policy_v1.py',R/'src/gradle_process_supervisor_v1.py',Path(__file__)]},'limitations':['No copied distribution/dependency cache qualification','No Java/EvoSuite generation command guard wired','No native test/provider or Gradle recipe qualification','No batch admission or benchmark result','No metric/parser changes']}
dump(O/'result.json',report);audit.log('B1_GRADLE_COMMAND_POLICY_STATIC_VALIDATED',result_sha256=sha(O/'result.json'),checks=len(checks),contexts=40,experiment_calls=0);print(json.dumps({k:v for k,v in report.items() if k not in {'metadata_contexts_validated','code_hashes'}},indent=2))

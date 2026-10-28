"""Pure adversarial validation of Gradle generation and context guards."""
import copy,json,sys
from pathlib import Path
from maven_adapter_v1 import R,JDK,WORKSPACE,sha,dump,GuardAbort,reviewer_options
from gradle_command_policy_v3 import CONTEXT,PRIVATE_HOME,GradleCommandPolicy,launcher_paths
from gradle_generation_argv_v1 import checked_gradle_generation_argv
from gradle_process_supervisor_v4 import GradleSupervisor,environment
from process_supervisor_v1 import Supervisor
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'validation/gradle_generation_envelope_v1';O.mkdir(exist_ok=False);checks=[]
jobs={j['sample_index_1based']:j for j in json.loads((R/'manifest300.json').read_text(encoding='utf-8'))}
contexts=json.loads(CONTEXT.read_text(encoding='utf-8'));java=(JDK/'bin/java.exe').resolve();launchers=launcher_paths()
def reject(name,fn):
 try:fn()
 except (GuardAbort,KeyError,FileNotFoundError):checks.append(name)
 else:raise AssertionError('Unsafe command accepted: '+name)
def setup(c):
 j=jobs[c['sample_index_1based']];out=O/f"sample{j['sample_index_1based']:03d}";module=out/'repo'/c['module_dir_relative_to_repo'];classes=module/'build/classes/java/main';classes.mkdir(parents=True)
 sentinel=classes/'guard-only.txt';sentinel.write_text('synthetic command validation; no Java bytecode or process',encoding='utf-8')
 cp=str(classes.resolve());guard=out/'classpath_guards/01.json';dump(guard,[{'path':cp,'kind':'directory','files':{'guard-only.txt':sha(sentinel)}}])
 focal=j['focal_path'].split('/src/main/java/',1)[1].removesuffix('.java').replace('/','.')
 raw=[str(java),'-jar',str(WORKSPACE/'scripts_v2/evosuite-1.2.0.jar'),'-class',focal,'-projectCP',cp,'-Dtest_dir='+str(module/'src/test/java'),'-Dreport_dir='+str(module/'evosuite-report'),*reviewer_options()]
 argv=checked_gradle_generation_argv(raw,j,out)
 lock={'gradle_user_home':str(PRIVATE_HOME.resolve()),'gradle_launchers':{k:str(v) for k,v in launchers.items()},'java_executable':str(java),'tool_hashes':{str(p):sha(p) for p in [java,*launchers.values()]},'gradle_context_path':str(CONTEXT.resolve()),'gradle_context_sha256':sha(CONTEXT),'admitted_sample_indices':[j['sample_index_1based']],'execution_scope':'runtime_qualification','Gradle_execution_admitted':False,'Gradle_runtime_qualified':False,'GPT_generation_authorized':False,'code_and_input_hashes':{str(guard.resolve()):sha(guard)},'generation_classpath_guard':str(guard.resolve()),'generation_attempt':1,'retry_evidence':None,'gradle_task_plans':{'generation':{'argv_tail':argv[1:],'timeout_seconds':240},'pit':{'argv_tail':[c['task_prefix']+'pitest'],'timeout_seconds':900}}}
 return j,out,module,lock,argv
for c in contexts:
 j,out,module,lock,argv=setup(c);p=GradleCommandPolicy(out,j,c,lock);assert p.validate(argv,module,240,'generation')[0]==argv
checks.append('all40 metadata-bound module/FQCN/seed/profile generation plans validated without processes')
c=contexts[0];j=jobs[c['sample_index_1based']];out=O/f"sample{j['sample_index_1based']:03d}";module=out/'repo'/c['module_dir_relative_to_repo']
# Preserve the final loop's values separately; reload this exact fixture setup.
c=contexts[-1];p=GradleCommandPolicy(out:=O/f"sample{c['sample_index_1based']:03d}",j:=jobs[c['sample_index_1based']],c,lock);module=out/'repo'/c['module_dir_relative_to_repo']
for name,change in [('assertions_disabled',lambda a:[x.replace('-Dassertions=true','-Dassertions=false') for x in a]),('changed_seed',lambda a:a[:-1]+['1']),('changed_budget',lambda a:[x.replace('-Dsearch_budget=60','-Dsearch_budget=120') for x in a]),('undeclared_parameter',lambda a:a+['-Dminimize=false']),('test_output_escape',lambda a:[x if not x.startswith('-Dtest_dir=') else '-Dtest_dir=D:/foreign/tests' for x in a]),('CP_injection',lambda a:[x if x!=argv[argv.index('-projectCP')+1] else 'D:/foreign/classes' for x in a])]:
 badargs=change(list(argv));bad=copy.deepcopy(lock);bad['gradle_task_plans']['generation']['argv_tail']=badargs[1:];bp=GradleCommandPolicy(out,j,c,bad)
 reject(name,lambda:bp.validate(badargs,module,240,'generation'))
reject('changed generation timeout',lambda:p.validate(argv,module,300,'generation'))
bad=copy.deepcopy(lock);bad['generation_attempt']=3;bp=GradleCommandPolicy(out,j,c,bad);reject('third attempt',lambda:bp.validate(argv,module,240,'generation'))
bad=copy.deepcopy(lock);bad['generation_attempt']=2;bad['retry_evidence']=str(out/'absent.json');bp=GradleCommandPolicy(out,j,c,bad);reject('retry without primary failure evidence',lambda:bp.validate(argv,module,240,'generation'))
wrong=copy.deepcopy(j);wrong['build_tool']='maven';reject('Maven job rejected by explicit Gradle argv guard',lambda:checked_gradle_generation_argv(argv[:-2],wrong,out))
assert GradleSupervisor.kill_owned is Supervisor.kill_owned
env=environment();assert env['JAVA_TOOL_OPTIONS']=='-Xbootclasspath/a:"'+str(JDK/'lib/tools.jar')+'"'
supervisor=GradleSupervisor(out,env,j,c);reject('no admission means no process',lambda:supervisor.run(argv,module,240,sha(java),{},stage='generation'))
assert not list(supervisor.command_root.iterdir());checks.append('owned-tree termination unchanged; exact JDK8 bootstrap; admission required before command record/process')
dump(O/'result.json',{'status':'PASS_STATIC_ONLY','checks':checks,'contexts':40,'processes_started':0,'benchmark_admitted':False,'sources':{str(R/'src'/n):sha(R/'src'/n) for n in ['gradle_generation_argv_v1.py','gradle_generation_plan_guard_v1.py','gradle_command_policy_v3.py','gradle_process_supervisor_v4.py','validate_gradle_generation_envelope_v1.py']}})
audit.log('B1_GRADLE_GENERATION_ENVELOPE_STATIC_PASS',result_sha256=sha(O/'result.json'),checks=len(checks),new_experiment_calls=0)
print(json.dumps({'status':'PASS_STATIC_ONLY','checks':checks,'contexts':40,'processes_started':0},indent=2))

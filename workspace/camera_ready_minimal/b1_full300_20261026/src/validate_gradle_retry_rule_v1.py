"""No-process positive/negative tests of the predeclared technical retry gate."""
import copy,json,os,sys
from pathlib import Path
from maven_adapter_v1 import R,JDK,WORKSPACE,sha,dump,GuardAbort,reviewer_options
from gradle_generation_argv_v1 import checked_gradle_generation_argv
from gradle_generation_plan_guard_v1 import validate
from gradle_command_policy_v3 import CONTEXT,PRIVATE_HOME
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
out=R/'validation/gradle_retry_rule_v1';out.mkdir(exist_ok=False)
c=next(x for x in json.loads(CONTEXT.read_text(encoding='utf-8')) if x['sample_index_1based']==4)
j=next(x for x in json.loads((R/'manifest300.json').read_text(encoding='utf-8')) if x['sample_index_1based']==4)
module=out/'repo'/c['module_dir_relative_to_repo'];classes=module/'build/classes/main';classes.mkdir(parents=True)
jar=next((PRIVATE_HOME/'caches/modules-2/files-2.1/junit/junit/4.13.2').glob('*/*.jar'))
cp=str(classes.resolve())+os.pathsep+str(jar.resolve())
raw=[str((JDK/'bin/java.exe').resolve()),'-jar',str(WORKSPACE/'scripts_v2/evosuite-1.2.0.jar'),'-class','com.github.SingleNumber.Solution','-projectCP',cp,'-Dtest_dir='+str(module/'src/test/java'),'-Dreport_dir='+str(module/'evosuite-report'),*reviewer_options()]
first=checked_gradle_generation_argv(raw,j,out);second=list(first);second[second.index('-projectCP')+1]=str(classes.resolve())
cmd=out/'commands/001';cmd.mkdir(parents=True);so=cmd/'stdout.txt';se=cmd/'stderr.txt';so.write_text('Technical error DisplayNameGenerator\n',encoding='utf-8');se.write_text('',encoding='utf-8')
receipt=out/'generation_attempts/01/invocation.json'
prior={'attempt':1,'seed':j['seed'],'timeout':False,'returncode':1,'native_test_exists':False,'stdout_path':str(so),'stderr_path':str(se),'stdout_sha256':sha(so),'stderr_sha256':sha(se),'logical_argv':first}
dump(receipt,prior);guard=out/'classpath_guards/02.json';dump(guard,[{'path':str(classes.resolve()),'kind':'directory','files':{}}])
lock={'generation_attempt':2,'generation_classpath_guard':str(guard.resolve()),'retry_evidence':str(receipt.resolve()),'code_and_input_hashes':{str(guard.resolve()):sha(guard),str(receipt.resolve()):sha(receipt)}}
assert validate(second,j,c,out,lock)==second
checks=['same-seed exact sanitizer after declared technical failure accepted without any Java call']
# Each negative case uses a separate receipt directory; original evidence stays intact.
def reject(name,changed,changed_argv=None):
 folder=out/'negative_cases'/name;folder.mkdir(parents=True);copyout=folder/'case';copyout.mkdir()
 # The guard requires the exact owned primary receipt location.
 dest=copyout/'generation_attempts/01/invocation.json';dump(dest,changed)
 bad=copy.deepcopy(lock);bad['retry_evidence']=str(dest.resolve());bad['code_and_input_hashes'][str(dest.resolve())]=sha(dest)
 try:validate(changed_argv or second,j,c,out,bad)
 except GuardAbort:return
 raise AssertionError(name+' accepted')
# Validate predicate behavior directly through immutable alternative complete fixture trees.
for name,change in [('successful_primary',{'returncode':0,'native_test_exists':True}),('timed_out_primary',{'timeout':True}),('different_seed',{'seed':1})]:
 altered={**prior,**change};dest=out/'negative_evidence'/name/'invocation.json';dump(dest,altered)
 # Keep original primary path fixed, substitute the data only in the read seam.
 import gradle_generation_plan_guard_v1 as guard_module
 original_load=guard_module.load
 def fake_load(path,altered=altered):return altered if Path(path).resolve()==receipt.resolve() else original_load(path)
 guard_module.load=fake_load
 try:
  try:validate(second,j,c,out,lock)
  except GuardAbort:checks.append(name+' rejected')
  else:raise AssertionError(name+' accepted')
 finally:guard_module.load=original_load
# Marker-independent score data cannot affect eligibility: no score is consulted.
for score in [0,100]:
 altered={**prior,'mutation_score_percent':score};original_load=guard_module.load
 def fake_load(path,altered=altered):return altered if Path(path).resolve()==receipt.resolve() else original_load(path)
 guard_module.load=fake_load
 try:assert validate(second,j,c,out,lock)==second
 finally:guard_module.load=original_load
checks.append('extraneous score0/100 does not alter technical retry eligibility')
report={'status':'PASS_PURE_VALIDATION','checks':checks,'processes_started':0,'source_sha256':sha(R/'src/gradle_generation_plan_guard_v1.py'),'test_seam':'read-only receipt loader substitution in this interpreter only; source files and actual evidence preserved'}
dump(out/'result.json',report);audit.log('B1_GRADLE_RETRY_RULE_STATIC_PASS',receipt_sha256=sha(out/'result.json'),processes_started=0);print(json.dumps(report,indent=2))

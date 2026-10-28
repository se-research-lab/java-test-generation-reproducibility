"""Explicit synthetic CP-file runtime qualification candidate; NEVER auto-run.

Parent must invoke only after the serial Maven batch is idle. The nonblocking
dispatcher mutex is acquired before mkdir or any fixture subprocess. No full
Maven admission or recovery of job012 is issued by this fixture.
"""
import copy,hashlib,json,msvcrt,os,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,JDK,MVN,GuardAbort,sha,dump
from b1_maven_commands_v3 import MavenCommands
from maven_controller_v2 import execute,archive,ensure
from checkpoint_archive_guard_v2 import verify as verify_archive
from classpath_transport_v1 import inflate,serialized_units,argv_sha256
from run_maven_b1_v2 import guards
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'validation/long_classpath_fixture_v1'

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()

class SyntheticLongClasspathCommands(MavenCommands):
 """Only this exact synthetic fixture may add duplicate SMALL pinned JARs."""
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.extension_done=False
  ensure(self.lock.get('scope')=='synthetic_long_classpath_fixture' and self.out==O.resolve(),'Synthetic CP extension outside exact scope')
  ensure(self.job['sample_index_1based']==0 and self.job['class_key']=='synthetic:fixture.BranchFixture','Synthetic CP identity mismatch')

 def run(self,argv,**kw):
  args=list(map(str,argv));exe=Path(args[0]).name.lower()
  if exe in {'java','java.exe'} and args[1:]!=['-version']:
   self.verify_lock()
   ensure(not self.extension_done and self.generations==0,'Long CP fixture admits first generation attempt only')
   ensure(args.count('-projectCP')==1 and '-seed' not in args,'Unexpected caller CP/seed shape')
   index=args.index('-projectCP')+1;original=args[index]
   jar=self.cache/'org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
   ensure(jar.is_file() and jar.stat().st_size<100000,'Fixture requires the small Hamcrest-core JAR')
   ensure(sha(jar)==self.cache_hashes[jar.relative_to(self.cache).as_posix()],'Synthetic duplicate JAR differs from pinned cache')
   added=0
   while serialized_units(args)<=33000:
    args[index]+=os.pathsep+str(jar);added+=1
    ensure(added<=1000,'Unexpected synthetic CP extension bound')
   ensure(added>0,'Fixture was already over-limit before deliberate synthetic extension')
   self.extension_done=True
   dump(self.out/'fixture_cp_extension.json',{'scope':'synthetic fixture only; not a benchmark configuration','duplicated_small_JAR':str(jar),'JAR_sha256':sha(jar),'JAR_bytes':jar.stat().st_size,'additional_duplicate_entries':added,'original_CP_sha256':hashlib.sha256(original.encode('utf-8')).hexdigest(),'extended_CP_sha256':hashlib.sha256(args[index].encode('utf-8')).hexdigest(),'serialized_before_seed_UTF16_units_including_NUL':serialized_units(args),'original_entries_preserved_as_prefix':args[index].startswith(original+os.pathsep),'seed_will_be_added_by_unchanged_external_guard':self.job['seed']})
  return super().run(args,**kw)

def copy_exclusive(source,target,expected):
 ensure(sha(source)==expected,'Known fixture source hash differs: '+str(source));target.parent.mkdir(parents=True,exist_ok=True)
 with source.open('rb') as f,target.open('xb') as t:shutil.copyfileobj(f,t)
 ensure(sha(target)==expected,'Fixture input copy differs')

def seal():
 """Retain any earlier controller index, then create a final complete index."""
 current=O/'artifact_manifest.json'
 if current.exists():
  number=1
  while (O/f'controller_artifact_manifest_{number:03d}.json').exists():number+=1
  previous=O/f'controller_artifact_manifest_{number:03d}.json';expected=sha(current)
  current.rename(previous);ensure(sha(previous)==expected,'Preserved controller archive differs')
 archive(O)
 return verify_archive(O)

def main():
 # Opening an existing lock file does not create the fixture or launch any tool.
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   prior_lock=load(R/'admission_maven_v2.json');guards(prior_lock)
   ensure(load(R/'validation/classpath_transport_v1/result.json')['status']=='PASS_STATIC_ONLY','Pure transport validation missing')
   ensure(load(R/'cache_preparation_v1/complete.json')['status']=='PASS','Private Maven cache incomplete')
   ensure(shutil.disk_usage(R).free>=prior_lock['minimum_free_bytes'],'Disk reserve reached before fixture')
   previous=R/'validation/maven_controller_fixture_v1'
   ensure(load(previous/'validation_result.json')['status']=='PASS','Known controller fixture did not pass')
   source_index={r['relative']:r for r in load(previous/'artifact_manifest.json')}
   sources=[('repo/src/main/java/fixture/BranchFixture.java','BranchFixture.java'),('pom_before_integration.xml','pom.xml'),('settings.xml','settings.xml')]
   for relative,_ in sources:ensure(sha(previous/relative)==source_index[relative]['sha256'],'Known fixture archive input changed')
   O.mkdir(parents=True,exist_ok=False);M=O/'repo';inputs=[]
   for relative,name in sources:
    source=previous/relative;backup=O/'fixture_inputs'/name;h=source_index[relative]['sha256'];copy_exclusive(source,backup,h)
    dest=M/'src/main/java/fixture/BranchFixture.java' if name=='BranchFixture.java' else M/'pom.xml' if name=='pom.xml' else O/'settings.xml'
    copy_exclusive(backup,dest,h);inputs.append({'source':str(source),'immutable_copy':str(backup),'live_copy':str(dest),'sha256':h,'source_index_sha256':sha(previous/'artifact_manifest.json')})
   dump(O/'fixture_inputs_manifest.json',inputs)
   job={'sample_index_1based':0,'seed':20261023,'class_key':'synthetic:fixture.BranchFixture','repo_id':'synthetic','module':'','build_tool':'maven','focal_path':'src/main/java/fixture/BranchFixture.java','focal_class':'BranchFixture','package':'fixture','selected_test_fqcn':'fixture.BranchFixture_ESTest','junit_version':'4.13.2','testng_version':None,'reused_result':{}}
   names=['run_long_classpath_fixture_v1.py','b1_maven_commands_v3.py','classpath_transport_v1.py','maven_controller_v2.py','checkpoint_archive_guard_v1.py','checkpoint_archive_guard_v2.py']
   paths=[R/'src'/name for name in names]+list((O/'fixture_inputs').glob('*'))+[O/'fixture_inputs_manifest.json',M/'src/main/java/fixture/BranchFixture.java',O/'settings.xml',previous/'validation_result.json',previous/'artifact_manifest.json',R/'validation/classpath_transport_v1/result.json']
   paths += [Path(r['source']) for r in inputs]
   admission=copy.deepcopy(prior_lock);admission.update(scope='synthetic_long_classpath_fixture',synthetic_execution_admitted=True,benchmark_admitted=False,GPT_generation_authorized=False,admitted_sample_indices=[0],job=job,fixture_only=True,no_job012_recovery=True)
   admission['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in paths})
   dump(O/'synthetic_admission.json',admission)
   def event(kind,**kw):
    with (O/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'timestamp_utc':now(),'kind':kind,**kw},ensure_ascii=False)+'\n')
    audit.log('B1_LONG_CP_FIXTURE_'+kind,**kw)
   commands=None
   try:
    commands=SyntheticLongClasspathCommands(O,job,O/'synthetic_admission.json',event)
    result=execute(O,job,commands,event)
    ensure(result['legacy_process_build']==1 and result['strict_measurement_evidence'],'Full lifecycle native-suite/PIT/JaCoCo evidence missing')
    ensure(result['focal_mutants']==result['killed_mutants']==6 and result['legacy_strict_mutation_percent']==100.0,'Known fixture positive-control result differs')
    ensure(result['source_guard']==result['production_bytecode_guard']=='PASS','Controller source/production-bytecode guard failed')
    generation=[r for r in commands.records if r['generation']]
    ensure(len(generation)==1 and commands.generations==1 and generation[0]['transport_applied'],'Expected exactly one CP-file generation')
    record=generation[0];transport=load(record['transport_manifest']);ensure(inflate(record['executed_argv'],transport,O)==record['argv'],'Logical/effective argv round-trip failed')
    ensure(all(sha(p)==h for p,h in record['process_input_hashes'].items()),'Pinned CP transport input drift')
    started=[]
    for plan in (O/'commands').glob('*/plan.json'):
     p=load(plan)
     if '-jar' in p['argv'] and (plan.parent/'started.json').exists():started.append(p)
    ensure(len(started)==1,'Expected exactly one actual EvoSuite process start')
    commands.verify_lock();guards(prior_lock)
    summary={'status':'PASS','qualification':'SYNTHETIC_LONG_CLASSPATH_RUNTIME_ONLY','benchmark_admitted':False,'new_benchmark_classes':0,'job012_retried':False,'GPT_API_calls':0,'generation_plans':commands.generations,'EvoSuite_processes_started':len(started),'transport_applied':True,'logical_argv_digest_roundtrip':True,'process_input_hashes_pinned':True,'logical_UTF16_units_including_NUL':transport['logical_command_UTF16_units_including_NUL'],'effective_UTF16_units_including_NUL':transport['effective_command_UTF16_units_including_NUL'],'focal_mutants':6,'killed_mutants':6,'score':100.0,'strict_measurement_evidence':True,'source_guard':result['source_guard'],'production_bytecode_guard':result['production_bytecode_guard'],'native_behavior_methods':result['inventory']['behavior_test_method_count'],'code_hashes':{str(p.resolve()):sha(p) for p in [R/'src/b1_maven_commands_v3.py',R/'src/classpath_transport_v1.py',Path(__file__)]}}
    dump(O/'validation_result.json',summary);event('VALIDATED',validation_result_sha256=sha(O/'validation_result.json'))
    archive_check=seal();audit.log('B1_LONG_CP_FIXTURE_SEALED',manifest_sha256=sha(O/'artifact_manifest.json'),validation_result_sha256=sha(O/'validation_result.json'))
    print(json.dumps({'validation':summary,'archive_verification':archive_check},indent=2))
   except BaseException as ex:
    dump(O/'failure.json',{'error_type':type(ex).__name__,'detail':str(ex),'generation_plans':commands.generations if commands else 0,'auto_retry':False,'benchmark_admitted':False,'job012_retried':False,'GPT_API_calls':0})
    event('FAILED',error_type=type(ex).__name__,detail=str(ex));seal();raise
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':main()

"""One compatibility diagnostic on frozen generated suite003; NEVER generation.
No benchmark replacement or general admission is issued by this script.
"""
import json,sys,shutil,copy,msvcrt
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
from maven_adapter_v1 import R,GuardAbort,sha,dump,generation_bindings,native_suite
from b1_maven_commands_v2 import MavenCommands
from maven_controller_v1 import source_hashes,dependency,effective,bytecode,archive,ensure
from measurement_parser_v1 import parse
from native_junit_policy_candidate_v1 import patch,compare,norm
from run_maven_b1_v1 import guards
from checkpoint_archive_guard_v1 import verify as verify_archive
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()

class MeasurementOnly(MavenCommands):
 def run(self,argv,**kw):
  ensure(Path(str(argv[0])).name.lower() in {'mvn','mvn.cmd'} or (Path(str(argv[0])).name.lower() in {'java','java.exe'} and list(argv[1:])==['-version']),'Diagnostic forbids generation/API; permits only read-only java -version')
  ensure('-DskipTests=true' not in argv,'Diagnostic forbids generation compile command')
  return super().run(argv,**kw)

def main():
 original_lock=load(R/'admission_maven_v1.json');guards(original_lock)
 ensure(load(R/'validation/native_junit_candidate_v1/result.json')['status']=='PASS','Missing static validation')
 O=R/'jobs/003_native_junit_diagnostic_v3';old=R/'jobs/003'
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   O.mkdir(exist_ok=False);j=load(old/'job_admission.json')['job'];M=O/'repo'/j['module']
   original_manifest=load(old/'artifact_manifest.json');report_before=verify_archive(old)
   dump(O/'checkpoint_archive_reconciliation.json',verify_archive(old))
   frozen=source_hashes(old/'repo');dump(O/'source_copy_manifest.json',frozen)
   for rel,h in frozen.items():
    src=old/'repo'/rel;dest=O/'repo'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    with src.open('rb') as f,dest.open('xb') as t:shutil.copyfileobj(f,t)
    ensure(sha(dest)==h,'Diagnostic copy mismatch')
   if (old/'settings.xml').exists():shutil.copyfile(old/'settings.xml',O/'settings.xml')
   lock=copy.deepcopy(original_lock);lock.update(scope='single diagnostic reuse003; not a benchmark replacement',admitted_sample_indices=[3],generation_authorized=False,diagnostic_only=True)
   for p in [Path(__file__),R/'src/native_junit_policy_candidate_v1.py',R/'validation/native_junit_candidate_v1/result.json',old/'artifact_manifest.json',old/'result.json',R/'src/checkpoint_archive_guard_v1.py']:
    lock['code_and_input_hashes'][str(p.resolve())]=sha(p)
   dump(O/'diagnostic_admission.json',lock)
   def event(kind,**kw):
    with (O/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kw})+'\n')
    audit.log('B1_NATIVE_JUNIT_DIAGNOSTIC_'+kind,**kw)
   commands=MeasurementOnly(O,j,O/'diagnostic_admission.json',event)
   try:
    test=j['selected_test_fqcn'];native=native_suite(M,test);ensure(native['complete'],'Missing frozen native suite')
    dump(O/'native_before.json',json.loads(json.dumps(native,default=str)))
    expected=dict(frozen);ns=generation_bindings(commands,O,event)
    args=['mvn',*(['-s',str(O/'settings.xml')] if (O/'settings.xml').exists() else []),'-Dtest='+test,*ns['common_maven_skip_args']()]
    before=dependency(commands,args,M,O,'before');eff=effective(commands,args,M,O,'before')
    ensure(patch(M/'pom.xml',O,before),'Expected missing JUnit4 condition not found')
    expected[(M/'pom.xml').relative_to(O/'repo').as_posix()]=sha(M/'pom.xml')
    after=dependency(commands,args,M,O,'after');aftereff=effective(commands,args,M,O,'after')
    delta=compare(before,after);ensure(norm(eff)==norm(aftereff),'Surefire changed');dump(O/'dependency_guard.json',delta)
    ensure(source_hashes(O/'repo')==expected,'Unexpected source delta before measurement')
    df=pd.DataFrame([{'Project':j['repo_id'],'Module':j['module'],'Focal_Class':j['focal_class'],'Test_Class':test.split('.')[-1],'Focal_Path':str(O/'repo'/j['focal_path']),'Test_Path':(M/'src/test/java'/Path(*test.split('.')).with_suffix('.java')).as_posix()}])
    gate=ns['run_maven_test_command'](str(M),df,'Windows')[0]
    ensure(source_hashes(O/'repo')==expected,'Measurement changed source');ensure(native_suite(M,test)['files']==native['files'],'Native suite changed')
    baseline=load(old/'production_generation_baseline.json');observed=bytecode(M);ensure(baseline==observed,'Production bytecode differs from frozen generation')
    for row in after['classpath']+after['compile_classpath']:ensure(sha(row['absolute_path'])==row['sha256'],'JAR changed during measurement')
    result={'purpose':'compatibility diagnostic only; not admitted benchmark result','source_checkpoint_result_sha256':sha(old/'result.json'),'generation_calls':0,'GPT_API_calls':0,'source_guard':'PASS','production_bytecode_guard':'PASS','dependency_guard':delta,'benchmark_replacement_admitted':False,**parse(M,j['focal_class'],j['package'],test,gate)}
    dump(O/'diagnostic_result.json',result);event('COMPLETE',result_sha256=sha(O/'diagnostic_result.json'));print(json.dumps(result,indent=2))
   except BaseException as ex:
    dump(O/'failure.json',{'error_type':type(ex).__name__,'detail':str(ex),'auto_resume':False,'generation_calls':0,'GPT_API_calls':0});event('FAILED',detail=str(ex));raise
   finally:archive(O)
   ensure(verify_archive(old)==report_before,'Original checkpoint changed')
   guards(original_lock)
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()

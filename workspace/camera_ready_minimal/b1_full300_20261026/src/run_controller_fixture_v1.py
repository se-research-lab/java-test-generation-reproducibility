"""One synthetic fixture through the actual controller and v2 command bridge."""
import json,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,JDK,MVN,sha,dump
from b1_maven_commands_v2 import MavenCommands
from maven_controller_v1 import execute
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
assert load(R/'validation/maven_runtime_fixture_v1/result.json')['status']=='PASS'
assert load(R/'inputs/snapshot_v3/complete.json')['status']=='PASS'
assert load(R/'cache_preparation_v1/complete.json')['status']=='PASS'
O=R/'validation/maven_controller_fixture_v1';O.mkdir(parents=True,exist_ok=False);M=O/'repo';(M/'src/main/java/fixture').mkdir(parents=True)
previous=R/'validation/maven_runtime_fixture_v1'
for src,dst in [(previous/'repo/src/main/java/fixture/BranchFixture.java',M/'src/main/java/fixture/BranchFixture.java'),(previous/'pom_before.xml',M/'pom.xml'),(previous/'settings.xml',O/'settings.xml')]:
 with src.open('rb') as f,dst.open('xb') as out:shutil.copyfileobj(f,out)
 assert sha(src)==sha(dst)
job={'sample_index_1based':0,'seed':20261023,'class_key':'synthetic:fixture.BranchFixture','repo_id':'synthetic','module':'','build_tool':'maven','focal_path':'src/main/java/fixture/BranchFixture.java','focal_class':'BranchFixture','package':'fixture','selected_test_fqcn':'fixture.BranchFixture_ESTest','junit_version':'4.13.2','testng_version':None,'reused_result':{}}
toolpaths=[JDK/'bin/java.exe',MVN,JDK/'lib/tools.jar',R.parents[1]/'scripts_v2/evosuite-1.2.0.jar',R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']
codes=['run_controller_fixture_v1.py','maven_controller_v1.py','b1_maven_commands_v2.py','maven_adapter_v1.py','measurement_parser_v1.py','process_supervisor_v1.py','pom_integration_guard_v1.py']
inputs=[R/'src'/n for n in codes]+[M/'src/main/java/fixture/BranchFixture.java',O/'settings.xml',R/'protocol.json',R/'audit/adapter_extraction_v1.json']+list((R/'adapters').glob('*.py'))
admission={'scope':'synthetic_controller_fixture','synthetic_execution_admitted':True,'benchmark_admitted':False,'GPT_generation_authorized':False,'admitted_sample_indices':[0],'cache':str(R/'cache_preparation_v1/maven_cache'),'cache_manifest_sha256':sha(B/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json'),'tool_hashes':{str(p.resolve()):sha(p) for p in toolpaths},'code_and_input_hashes':{str(p.resolve()):sha(p) for p in inputs},'job':job}
dump(O/'synthetic_admission.json',admission)
def event(kind,**kw):
 with (O/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'timestamp_utc':datetime.now(timezone.utc).isoformat(),'kind':kind,**kw},ensure_ascii=False)+'\n')
 audit.log('B1_CONTROLLER_FIXTURE_'+kind,**kw)
commands=MavenCommands(O,job,O/'synthetic_admission.json',event)
try:
 result=execute(O,job,commands,event)
 assert result['strict_measurement_evidence'] and result['killed_mutants']>0 and result['inventory']['behavior_test_method_count']>0
 summary={'status':'PASS','controller_sha256':sha(R/'src/maven_controller_v1.py'),'commands_sha256':sha(R/'src/b1_maven_commands_v2.py'),'generation_calls':commands.generations,'score':result['legacy_strict_mutation_percent'],'mutants':result['focal_mutants'],'dependency_audits':True,'effective_POM_audit':True,'source_guard':result['source_guard'],'production_bytecode_guard':result['production_bytecode_guard'],'benchmark_admitted':False,'new_benchmark_classes':0,'GPT_API_calls':0}
 dump(O/'validation_result.json',summary);event('VALIDATED',**summary);print(json.dumps(summary,indent=2))
except BaseException as ex:
 dump(O/'failure.json',{'error_type':type(ex).__name__,'detail':str(ex),'generation_calls':commands.generations,'auto_retry':False});event('FAILED',error_type=type(ex).__name__,detail=str(ex));raise
finally:
 old=R/'status.json';before=old.read_bytes()
 with (O/'status_before_fixture_update.json').open('xb') as f:f.write(before)
 s=json.loads(before);s.update(updated_utc=datetime.now(timezone.utc).isoformat(),phase='CONTROLLER FIXTURE COMPLETE; SEE VALIDATION',fixture_EvoSuite_calls=1+commands.generations,new_EvoSuite_calls=1+commands.generations,new_completed=0,benchmark_admitted=False,running=0)
 tmp=O/'status_after.tmp';dump(tmp,s);tmp.replace(old)

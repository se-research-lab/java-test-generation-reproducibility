"""One explicit synthetic generation-to-measurement qualification.

Metadata row4 binds paths/wrapper/seed only. The actual focal source is the
saved three-branch synthetic BranchFixture, not a corpus source. No result is
written below jobs or admitted into E1. No automatic retry of this invocation.
"""
import copy,json,msvcrt,shutil,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump,GuardAbort
from gradle_command_policy_v3 import CONTEXT
from gradle_execution_v2 import execute
from gradle_measurement_parser_v1 import parse
from gradle_sealed_inputs_v1 import collect
from maven_controller_v2 import archive
from parallel_pin_verify_v1 import verify_pins
from run_maven_b1_v3 import guards
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'validation/gradle_controller_runtime_fixture_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
 mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
 try:
  assert not O.exists(),'Preserve prior fixture; no implicit retry'
  guards(load(R/'admission_maven_v6.json'))
  qualification_paths=[];parser_results=[]
  for version in ['2.13','5.2.1','6.9.4','8.14.4']:
   q=R/'validation/gradle_native_runtime_fixture_v7'/('gradle_'+version)
   assert load(q/'result.json')['status']=='PASS_SYNTHETIC_NATIVE_MEASUREMENT_ONLY'
   proto=load(q/'protocol.json');assert proto['input_pins'][str((R/'src/gradle_native_recipe_v7.py').resolve())]==sha(R/'src/gradle_native_recipe_v7.py')
   verify_pins({str(q/row['relative']):row['sha256'] for row in load(q/'artifact_manifest.json')})
   context=next(c for c in load(CONTEXT) if c['Gradle_version']==version)
   fake={'selected_test_fqcn':'fixture.BranchFixture_ESTest','focal_class':'BranchFixture','package':'fixture'}
   positive=parse(q/'repo'/context['module_dir_relative_to_repo'],q/'recipe_measure/measure/evidence',fake,True)
   negative=parse(q/'repo'/context['module_dir_relative_to_repo'],q/'recipe_measure/measure/evidence',fake,False)
   assert positive['strict_measurement_evidence'] and positive['focal_mutants']>0 and positive['mutation_score_percent']>0
   assert negative['legacy_strict_mutation_percent']==0 and negative['mutation_score_percent']==positive['mutation_score_percent']
   parser_results.append({'version':version,'suite':positive['strict_suite_evidence'],'mutants':positive['focal_mutants'],'raw_score':positive['mutation_score_percent'],'gate_false_strict_zero':True})
   qualification_paths += [q/'result.json',q/'protocol.json',q/'artifact_manifest.json']
  context=next(c for c in load(CONTEXT) if c['sample_index_1based']==4)
  job=copy.deepcopy(next(j for j in load(R/'manifest300.json') if j['sample_index_1based']==4))
  job.update(focal_class='BranchFixture',focal_path=context['module_dir_relative_to_repo']+'/src/main/java/fixture/BranchFixture.java',selected_test_fqcn='fixture.BranchFixture_ESTest',package='fixture',synthetic_fixture=True)
  O.mkdir(exist_ok=False);module=O/'repo'/context['module_dir_relative_to_repo'];source=module/'src/main/java/fixture/BranchFixture.java';source.parent.mkdir(parents=True)
  saved=R/'validation/long_classpath_fixture_v1/repo/src/main/java/fixture/BranchFixture.java'
  expected=next(r for r in load(R/'validation/long_classpath_fixture_v1/artifact_manifest.json') if r['relative']=='repo/src/main/java/fixture/BranchFixture.java')['sha256'];assert sha(saved)==expected
  with saved.open('rb') as src,source.open('xb') as dst:shutil.copyfileobj(src,dst)
  assert sha(source)==expected
  (module/'settings.gradle').write_text("rootProject.name = 'b1-synthetic-controller-fixture'\n",encoding='utf-8')
  (module/'build.gradle').write_text("buildscript { repositories { mavenCentral() } }\napply plugin: 'java'\nsourceCompatibility = '1.8'\ntargetCompatibility = '1.8'\nrepositories { mavenCentral() }\ndependencies { testCompile 'junit:junit:4.13.2' }\n",encoding='utf-8')
  pins,tools=collect([Path(__file__),saved,*qualification_paths,R/'validation/gradle_generation_envelope_v1/result.json',R/'validation/parallel_pin_verify_v1/result.json'])
  admission={'execution_scope':'runtime_qualification','fixture_only':True,'Gradle_execution_admitted':True,'Gradle_benchmark_admitted':False,'Gradle_runtime_qualified':False,'GPT_generation_authorized':False,'code_and_input_hashes':pins,'tool_hashes':tools,'metadata_binding_only_sample_index':4,'actual_fixture':'fixture.BranchFixture','real_benchmark_row_executed':False,'generation_profile':'unchanged E49 reviewer assertions;60s search,240s external timeout;seed metadata row4','max_generation_attempts':2,'retry_policy':'same-seed exact predeclared sanitizer marker only; no score retry','parser_checks':parser_results,'no_corpus_admission':True}
  ap=O/'admission.json';dump(ap,admission)
  def event(kind,**kw):
   with (O/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':datetime.now(timezone.utc).isoformat(),'kind':kind,**kw},ensure_ascii=False)+'\n')
   audit.log('B1_GRADLE_CONTROLLER_SYNTHETIC_'+kind,**kw)
   if kind in {'STAGE','COMMAND_STARTED'}:
    status=load(R/'status.json');calls=sum(1 for p in (O/'commands').glob('*/plan.json') if '-jar' in load(p)['argv'] and (p.parent/'started.json').exists())
    status.update(phase='GRADLE_CONTROLLER_SYNTHETIC / '+str(kw.get('stage',kind)),updated_utc=datetime.now(timezone.utc).isoformat(),running=0,benchmark_admitted=False,active_sample_index=None,fixture_EvoSuite_calls=3+calls,new_EvoSuite_calls=status['benchmark_EvoSuite_calls']+3+calls)
    status['blockers']=['Native measurement4wrapper PASS; đang kiểm controller sinh→đo trên fixture','Không dùng fixture làm kết quả của300class','GPT/E49 và20Maven deferred giữ nguyên']
    publish_json(R/'status.json',status,label='gradle_controller_fixture_v1')
  audit.log('B1_GRADLE_CONTROLLER_SYNTHETIC_ADMITTED_ONCE',admission_sha256=sha(ap),script_sha256=sha(__file__),actual_fixture='fixture.BranchFixture',corpus_rows=0,max_search_attempts=2)
  try:
   result=execute(O,job,context,ap,event)
   assert result['generation_success'] and result['generation_calls']==1 and result['legacy_process_build']==1 and result['strict_measurement_evidence'] and result['focal_mutants']>0 and result['killed_mutants']>0,'Synthetic full chain did not pass; no benchmark admission'
   guards(load(R/'admission_maven_v6.json'))
   source_home=Path('C:/Users/admin/.gradle');cache=load(R/'cache_preparation_gradle_v1/recovery_v2/manifest.json');verify_pins({str((source_home/r['relative']).resolve()):r['sha256'] for r in cache})
   receipt={'status':'PASS_SYNTHETIC_GENERATION_AND_MEASUREMENT','actual_fixture':'fixture.BranchFixture','real_benchmark_rows':0,'new_EvoSuite_calls':result['generation_calls'],'GPT_API_calls':0,'source_native_and_bytecode_guards':'PASS','all_original_cache_files_unchanged':True,'controller_result_sha256':sha(O/'result.json'),'controller_archive_sha256':sha(O/'artifact_manifest.json'),'admission_sha256':sha(ap),'controller_sha256':sha(R/'src/gradle_execution_v2.py'),'parser_checks':parser_results,'Gradle_benchmark_admitted':False}
   target=R/'validation/gradle_controller_runtime_fixture_v1_qualification.json';dump(target,receipt);audit.log('B1_GRADLE_CONTROLLER_SYNTHETIC_PASS',receipt_sha256=sha(target));print(json.dumps(receipt,indent=2))
  except BaseException as ex:
   failure=R/'validation/gradle_controller_runtime_fixture_v1_failure.json';dump(failure,{'type':type(ex).__name__,'detail':str(ex),'traceback':traceback.format_exc(),'automatic_retry':False,'benchmark_admitted':False})
   if not (O/'artifact_manifest.json').exists():archive(O)
   audit.log('B1_GRADLE_CONTROLLER_SYNTHETIC_FAILED',receipt_sha256=sha(failure));raise
 finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

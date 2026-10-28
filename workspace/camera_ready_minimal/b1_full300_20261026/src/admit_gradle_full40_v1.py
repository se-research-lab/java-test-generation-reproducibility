"""Seal the user's authorized, one-pass E-only Gradle40 run before outcomes.
Does not start any process. No admission without every required qualification.
"""
import ast,json,msvcrt,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump,reviewer_options
from gradle_command_policy_v3 import CONTEXT
from gradle_sealed_inputs_v1 import collect
from gradle_process_supervisor_v5 import environment
from parallel_pin_verify_v1 import verify_pins
from run_maven_b1_v3 import guards
from run_remaining_maven153_v6 import counts
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
A=R/'admission_gradle_full40_v1.json'
with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
 mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
 try:
  assert not A.exists(),'Never overwrite an admission'
  guards(load(R/'admission_maven_v6.json'))
  jobs=load(R/'manifest300.json');terminal,deferred,unattempted=counts(jobs)
  assert len(terminal)==191 and len(deferred)==20 and not unattempted,'Maven baseline differs'
  assert sum(bool(j['reused_result']) for j in jobs)==49
  selected=[j for j in jobs if j['build_tool']=='gradle'];contexts=load(CONTEXT)
  assert len(selected)==len(contexts)==40 and [j['sample_index_1based'] for j in selected]==[c['sample_index_1based'] for c in contexts]
  assert all(not (R/'jobs'/f"{j['sample_index_1based']:03d}_gradle_v1").exists() for j in selected),'Gradle class already attempted before seal'
  meta={x['sample_index_1based']:x for x in load(R/'inputs/context251_v1/manifest.json')}
  for j,c in zip(selected,contexts):
   fqcn=j['focal_path'].split('/src/main/java/',1)[1].removesuffix('.java').replace('/','.')
   assert meta[j['sample_index_1based']]['selected_test_fqcn']==fqcn+'_ESTest'
   assert j['seed']==c['original_seed']==20261023+j['sample_index_1based'] and j['module']==c['module_dir_relative_to_repo']
  static=R/'validation/gradle_generation_envelope_v1/result.json';retry=R/'validation/gradle_retry_rule_v1/result.json';positive=R/'validation/gradle_controller_runtime_fixture_v1_qualification.json'
  assert load(static)['status']=='PASS_STATIC_ONLY' and load(retry)['status']=='PASS_PURE_VALIDATION'
  q=load(positive);assert q['status']=='PASS_SYNTHETIC_GENERATION_AND_MEASUREMENT' and q['controller_sha256']==sha(R/'src/gradle_execution_v2.py') and q['real_benchmark_rows']==0
  assert q['controller_result_sha256']==sha(R/'validation/gradle_controller_runtime_fixture_v1/result.json') and q['controller_archive_sha256']==sha(R/'validation/gradle_controller_runtime_fixture_v1/artifact_manifest.json')
  verify_pins({str(R/'validation/gradle_controller_runtime_fixture_v1'/x['relative']):x['sha256'] for x in load(R/'validation/gradle_controller_runtime_fixture_v1/artifact_manifest.json')})
  qualification=[]
  for version in ['2.13','5.2.1','6.9.4','8.14.4']:
   p=R/'validation/gradle_native_runtime_fixture_v7'/('gradle_'+version)
   assert load(p/'result.json')['status']=='PASS_SYNTHETIC_NATIVE_MEASUREMENT_ONLY'
   verify_pins({str(p/x['relative']):x['sha256'] for x in load(p/'artifact_manifest.json')})
   qualification += [p/'result.json',p/'protocol.json',p/'artifact_manifest.json']
  assert set(reviewer_options())==set(load(R/'protocol.json')['generation_options'])
  env=environment();assert not [k for k in env if any(x in k.upper() for x in ['TOKEN','SECRET','PASSWORD','CREDENTIAL','APIKEY','ACCESS_KEY','PRIVATE_KEY'])],'Unqualified credential-like environment name; do not print values or execute'
  source_cache=Path('C:/Users/admin/.gradle');rows=load(R/'cache_preparation_gradle_v1/recovery_v2/manifest.json');verify_pins({str((source_cache/r['relative']).resolve()):r['sha256'] for r in rows})
  extra=[Path(__file__),R/'src/run_gradle_full40_v2.py',R/'src/run_maven_b1_v2.py',R/'src/run_maven_b1_v3.py',R/'src/run_remaining_maven153_v6.py',R/'GRADLE40_FROZEN_PROTOCOL_V1.md',R/'inputs/context251_v1/manifest.json',R/'inputs/snapshot_v3/index.json',R/'inputs/snapshot_v3/complete.json',static,retry,positive,R/'validation/parallel_pin_verify_v1/result.json',R/'validation/gradle_controller_runtime_fixture_v1/result.json',R/'validation/gradle_controller_runtime_fixture_v1/artifact_manifest.json',R/'validation/gradle_controller_runtime_fixture_v1/admission.json',R/'EXPERIMENT_CONFIGURATION_FREEZE_20261026.json',*qualification]
  extra += [R/c['snapshot_evidence']['manifest_relative_to_B1'] for c in contexts]
  pins,tools=collect(extra)
  for p in [R/'src/run_gradle_full40_v2.py',R/'src/gradle_execution_v2.py']:ast.parse(p.read_text(encoding='utf-8'))
  assert shutil.disk_usage(R).free>13_000_000_000,'Insufficient initial disk headroom'
  record={'schema':'B1_Gradle_full40_frozen_v1','sealed_utc':datetime.now(timezone.utc).isoformat(),'execution_scope':'benchmark','Gradle_execution_admitted':True,'Gradle_benchmark_admitted':True,'Gradle_runtime_qualified':True,'GPT_generation_authorized':False,'admitted_sample_indices':[j['sample_index_1based'] for j in selected],'workers':1,'code_and_input_hashes':pins,'tool_hashes':tools,'generation_options':reviewer_options(),'seed_rule':'20261023 + original 1-based index','generation_search_seconds':60,'generation_timeout_seconds':240,'max_generation_attempts':2,'retry':'exact predeclared E49 technical markers + exact sanitizer, same seed; no timeout/score retry','Gradle_stage_timeout_seconds':900,'measurement_recipe_source_sha256':sha(R/'src/gradle_native_recipe_v7.py'),'native_source_repair_allowed':False,'dependency_version_upgrade_allowed':False,'outcome_driven_configuration_changes_allowed':False,'measurement_retry_allowed':False,'automatic_resume_allowed':False,'baseline':{'E49_reused':49,'Maven_new_terminal':191,'Maven_deferred_unscored':20,'Maven_deferred_indices':deferred,'GPT':'frozen original300; no generation/remeasurement; RQ1-3 unchanged'},'terminal_selection':'first frozen lifecycle; attempt2 only technical generation retry before measurement; no result maximization','unscored_deferrals':'offline/toolchain unavailable; missing measurement dependency audit; unsupported existing JUnit; stale prior native suite','other_guard_failures':'stop whole invocation; preserve all evidence; no auto restart','minimum_free_bytes':12000000000,'original_cache_full_byte_checks':'before admission and after full pass; every immutable artifact pinned before commands','qualification_receipt_sha256':sha(positive),'status_before_first_corpus_class':'ALL40_UNATTEMPTED','full300_complete':False,'not_preregistered_before_E0':'post-review protocol; synthetic debugging outcomes already inspected'}
  dump(A,record)
  out=R/'audit/gradle_full40_seal_v1';out.mkdir(exist_ok=False)
  dump(out/'seal_receipt.json',{'admission_sha256':sha(A),'code_input_pins':len(pins),'classes':40,'original_source_cache_unchanged':True,'new_Java_calls':0,'new_EvoSuite_calls':0,'GPT_API_calls':0,'baseline_terminal':240,'baseline_deferred_Maven':20})
  audit.log('B1_GRADLE_FULL40_SEALED_BEFORE_FIRST_CLASS',admission_sha256=sha(A),classes=40,code_input_pins=len(pins),Maven_unscored_preserved=20,GPT_generation_authorized=False)
  print(json.dumps(load(out/'seal_receipt.json'),indent=2))
 finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

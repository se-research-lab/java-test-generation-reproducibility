"""Seal a transparent post-checkpoint native JUnit integration amendment."""
import ast,json,sys,copy
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from checkpoint_archive_guard_v2 import verify
from run_maven_b1_v2 import guards,project
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
original=load(R/'admission_maven_v1.json');guards(original)
diagnostic=R/'jobs/003_native_junit_diagnostic_v3';raw=load(diagnostic/'diagnostic_result.json')
assert raw['strict_measurement_evidence'] and raw['source_guard']=='PASS' and raw['production_bytecode_guard']=='PASS'
assert raw['generation_calls']==raw['GPT_API_calls']==0
assert load(R/'validation/native_junit_candidate_v1/result.json')['status']=='PASS'
assert not load(R/'audit/native_junit_scope_v1.json')['accepted49_without_junit4']
reports={str(folder.relative_to(R)):verify(folder) for folder in [R/'jobs/003',diagnostic]}
dump(R/'audit/native_junit_amendment_archive_checks_v2.json',reports)
names=['admit_maven_b1_v2.py','run_maven_b1_v2.py','maven_controller_v2.py','native_junit_policy_candidate_v1.py','checkpoint_archive_guard_v1.py','checkpoint_archive_guard_v2.py']
paths=[R/'src'/n for n in names]
for p in paths:ast.parse(p.read_text(encoding='utf-8'))
controller=(R/'src/maven_controller_v2.py').read_text(encoding='utf-8')
assert controller.index('run_evosuite_generation_maven')<controller.index('native_junit_added=native_junit_patch')<controller.index("patch=policy_ns['patch_pom']")<controller.index('run_maven_test_command')
assert "event('JOB_TERMINAL'" in controller and controller.index("event('JOB_TERMINAL'")<controller.index(';archive(out);return result')
paths += [R/'MAVEN_NATIVE_JUNIT_AMENDMENT_V2.md',R/'audit/native_junit_independent_review_v1.md',R/'validation/native_junit_candidate_v1/result.json',R/'audit/native_junit_scope_v1.json',R/'audit/native_junit_amendment_archive_checks_v2.json',diagnostic/'diagnostic_result.json',diagnostic/'artifact_manifest.json',diagnostic/'dependency_guard.json',R/'jobs/003/result.json',R/'jobs/003/artifact_manifest.json']
oldj=load(R/'jobs/003/job_admission.json')['job']
mapping={'amendment':'Maven native JUnit test dependency v2','decision_utc':datetime.now(timezone.utc).isoformat(),'known_initial_outcome':{'gate':0,'reason':'missing org.junit','path':'jobs/003/result.json','sha256':sha(R/'jobs/003/result.json')},'known_diagnostic_outcome':{'gate':raw['legacy_process_build'],'score':raw['legacy_strict_mutation_percent'],'focal_mutants':raw['focal_mutants']},'rule':'Uniform minimal test-only nativeJUnit condition for all remaining Maven jobs; not maximum score selection; original attempt retained','overrides':[{'sample_index_1based':3,'class_key':oldj['class_key'],'seed':oldj['seed'],'generation_evidence':'jobs/003','measurement_result':'jobs/003_native_junit_diagnostic_v3/diagnostic_result.json','measurement_sha256':sha(diagnostic/'diagnostic_result.json'),'supersedes_measurement_only':'jobs/003/result.json','generation_calls_total':1}],'accepted49_noop':49,'GPT_changes':0,'paper_updated':False}
dump(R/'measurement_result_map_v2.json',mapping);paths.append(R/'measurement_result_map_v2.json')
lock=copy.deepcopy(original);lock.update(created_utc=datetime.now(timezone.utc).isoformat(),scope='Maven211 with disclosed post-checkpoint native JUnit integration amendmentv2',first_invocation_max_jobs=2,framework_policy='E49 policy preserved; after generation only, supply missing resolved JUnit4 at test scope under pinned candidate rule. No upgrades/providers/business dependency changes. Each runtime outcome evidence audited; JUnit5 not presumed qualified by TestNG003.',prior_admission_sha256=sha(R/'admission_maven_v1.json'),known_before_amendment=mapping['known_diagnostic_outcome'],Gradle_admitted=False)
lock['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in paths})
dump(R/'admission_maven_v2.json',lock);guards(lock);project('AMENDMENT_V2_ADMITTED_CHECKPOINT_MAX2')
audit.log('B1_MAVEN_AMENDMENT_V2_ADMITTED',admission_sha256=sha(R/'admission_maven_v2.json'),measurement_map_sha256=sha(R/'measurement_result_map_v2.json'),known_003_outcome=mapping['known_diagnostic_outcome'],first_invocation_max_jobs=2,accepted49_noop=True,GPT_changes=0)
print('Maven amendmentv2 admitted; first invocation max2; diagnostic003 retained and mapped; GPT/49 guardsPASS')

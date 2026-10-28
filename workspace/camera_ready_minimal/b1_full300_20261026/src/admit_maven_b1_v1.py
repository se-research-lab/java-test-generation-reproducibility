"""Seal Maven-only execution admission before any new benchmark outcomes."""
import json,sys,ast
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,JDK,MVN,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
fixture=load(R/'validation/maven_controller_fixture_v1/validation_result.json');assert fixture['status']=='PASS'
assert sha(R/'src/maven_controller_v1.py')==fixture['controller_sha256']
assert sha(R/'src/b1_maven_commands_v2.py')==fixture['commands_sha256']
assert not load(R/'audit/maven_runtime_configs_v1.json')['unqualified_class_indices']
for row in load(R/'audit/input_lock.json'):assert sha(row['path'])==row['sha256']
audit.verify()
jobs=load(R/'manifest300.json');indices=[j['sample_index_1based'] for j in jobs if j['build_tool']=='maven' and not j['reused_result']];assert len(indices)==211 and indices==sorted(indices)
assert not list((R/'jobs').glob('*/result.json')) if (R/'jobs').exists() else True
names=['run_maven_b1_v1.py','admit_maven_b1_v1.py','maven_controller_v1.py','b1_maven_commands_v2.py','maven_adapter_v1.py','measurement_parser_v1.py','process_supervisor_v1.py','pom_integration_guard_v1.py','prepare_sandbox_v1.py','snapshot_store_v1.py']
paths=[R/'src'/n for n in names]+list((R/'adapters').glob('*.py'))
for p in paths:ast.parse(p.read_text(encoding='utf-8'))
paths += [R/'manifest300.json',R/'protocol.json',R/'inputs/snapshot_v3/index.json',R/'inputs/snapshot_v3/complete.json',R/'inputs/context251_v1/manifest.json',R/'inputs/context251_v1/summary.json',R/'audit/adapter_extraction_v1.json',R/'audit/adapter_backup_manifest_v2.json',R/'backups/accepted49_adapter/src/junit_method_inventory_v1.py',R/'audit/maven_runtime_configs_v1.json',R/'validation/maven_controller_fixture_v1/validation_result.json',R/'cache_preparation_v1/complete.json',R/'cache_preparation_v1/protocol.json']
toolpaths=[JDK/'bin/java.exe',MVN,JDK/'lib/tools.jar',R.parents[1]/'scripts_v2/evosuite-1.2.0.jar',R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']
record={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Maven211 continuation compatible with accepted49','benchmark_admitted':True,'GPT_generation_authorized':False,'admitted_sample_indices':indices,'workers':1,'first_invocation_max_jobs':1,'checkpoint_policy':'first remaining original-index class; retain its result regardless of outcome; no automatic resume of interrupted jobs','minimum_free_bytes':12_000_000_000,'cache':str(R/'cache_preparation_v1/maven_cache'),'cache_manifest_sha256':sha(B/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json'),'tool_hashes':{str(p.resolve()):sha(p) for p in toolpaths},'code_and_input_hashes':{str(p.resolve()):sha(p) for p in paths},'scope_limits':['Gradle40 not admitted','all failures retained, integrity failures halt unscored','no GPT generation or remeasurement','no paper edits until final audit','no prospective preregistration or assertion-only causal-effect claim'],'framework_policy':'Preserve native JUnit4 E49 integration and frozen historical project metadata; no repair/upgrade of JUnit5/TestNG projects outside conditional E49 policy. Discovered measurement incompatibility is logged, not silently repaired.'}
dump(R/'admission_maven_v1.json',record);audit.log('B1_MAVEN211_ADMITTED',sha256=sha(R/'admission_maven_v1.json'),first_sample_index=indices[0],n=211,first_invocation_max_jobs=1,GPT_authorized=False,Gradle_admitted=False)
print(json.dumps({'admission':'Maven211 only','first_sample_index':indices[0],'first_invocation_max_jobs':1,'GPT_API_calls':0},indent=2))

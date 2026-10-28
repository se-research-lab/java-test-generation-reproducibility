"""Assess the missing native JUnit4 integration without rerunning or editing tests."""
import json,sys
from collections import Counter
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
jobs=load(B/'e49_driver/input_manifest49.json');rows=[]
for j in jobs:
 out=B/'e49_measurement_compat_v1/jobs'/f"{j['job_index']:02d}"
 dep=load(out/'before_dependency.json');cp=dep['classpath'];junit=[r for r in cp if r['path'].startswith('junit/junit/')];testng=[r for r in cp if '/testng/' in r['path']]
 rows.append({'job_index':j['job_index'],'class_key':j['class_key'],'junit_metadata':j.get('junit_version'),'testng_metadata':j.get('testng_version'),'has_JUnit4_dependency':bool(junit),'has_TestNG_dependency':bool(testng),'JUnit_paths':[r['path'] for r in junit],'TestNG_paths':[r['path'] for r in testng],'before_dependency_sha256':audit.sha(out/'before_dependency.json')})
current=R/'jobs/003';result=load(current/'result.json');cp=load(current/'before_dependency.json')['classpath']
ctx=load(R/'inputs/context251_v1/manifest.json');frameworks=Counter(('JUnit'+str(r['junit_version']) if r['junit_version'] else 'no-JUnit')+('/TestNG'+str(r['testng_version']) if r['testng_version'] else '') for r in ctx)
report={'status':'READ_ONLY_AUDIT','accepted49':rows,'accepted49_without_junit4':[r['job_index'] for r in rows if not r['has_JUnit4_dependency']],'accepted49_with_testng':[r['job_index'] for r in rows if r['has_TestNG_dependency']],'new251_framework_counts':dict(frameworks),'checkpoint003':{'generation_success':result['generation_success'],'generation_calls':result['generation_calls'],'source_guard':result['source_guard'],'bytecode_guard':result['production_bytecode_guard'],'build_gate':result['legacy_process_build'],'JUnit4_in_resolved_test_classpath':any(r['path'].startswith('junit/junit/') for r in cp),'TestNG_in_resolved_test_classpath':any('/testng/' in r['path'] for r in cp),'failure_stage':'testCompile','observed_error':'package org.junit does not exist','result_sha256':audit.sha(current/'result.json')},'next_policy_not_admitted':['Evaluate test-scope native JUnit4 dependency only if missing from resolved test CP','Qualify Surefire native JUnit4 discovery in TestNG/JUnit5 project without converting original tests','Qualify PIT provider selection with original business dependency/compile closure unchanged','Check policy condition against all49 before claiming reuse','If adopted, pin amendment before remaining benchmark executions; reuse003 native generation, retain old measurement as diagnostic; no favorable outcome selection'],'new_experiment_calls':0,'GPT_changes':0}
dest=R/'audit/native_junit_scope_v1.json'
with dest.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
audit.log('B1_NATIVE_JUNIT_SCOPE_AUDIT',report_sha256=audit.sha(dest),without_JUnit4=report['accepted49_without_junit4'],with_TestNG=report['accepted49_with_testng'],experimental_calls=0)
print(json.dumps({k:v for k,v in report.items() if k!='accepted49'},indent=2))

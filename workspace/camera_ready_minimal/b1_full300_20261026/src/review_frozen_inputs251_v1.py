"""Read frozen manifests to enumerate sandbox admission hazards before any benchmark."""
import json,sys,sqlite3,hashlib
from pathlib import Path,PurePosixPath
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
S=R/'inputs/snapshot_v3';complete=load(S/'complete.json');assert complete['status']=='PASS'
assert audit.sha(S/'index.json')==complete['index_sha256']
jobs=load(R/'manifest300.json');contexts={r['sample_index_1based']:r for r in load(R/'inputs/context251_v1/manifest.json')}
maps={i:r for r in load(S/'index.json') for i in r['class_indices']};exclude={'.git','.gradle','.evosuite','target','build','evosuite-tests','evosuite-report'}
rows=[]
for j in jobs:
 if j['reused_result']:continue
 i=j['sample_index_1based'];mapping=maps[i];p=R/mapping['manifest'];assert audit.sha(p)==mapping['sha256'];m=load(p);ctx=contexts[i]
 files={r['relative']:r for r in m['files'] if not any(x in exclude for x in PurePosixPath(r['relative']).parts[:-1])}
 prior=ctx['prior_synthesized_test_relative'];focal=files.get(j['focal_path']);assert focal and focal['sha256']==j['source_candidate']['focal_sha256']
 assert prior in files,'Prior test missing from frozen source'
 stale=[n for n in files if '/src/test/java/' in '/'+n and n.endswith(('_ESTest.java','_ESTest_scaffolding.java'))]
 external_launch=[n for n in files if n.endswith(('.mvn/jvm.config','.mvn/maven.config','.mvn/extensions.xml','gradle.properties'))]
 descriptor=(PurePosixPath(j['module'])/'pom.xml').as_posix()
 concerns=[]
 if stale:concerns.append('stale_native_test_requires_review')
 if j['build_tool']=='maven' and descriptor not in files:concerns.append('module_POM_missing')
 if external_launch:concerns.append('project_runtime_config_requires_review')
 if ctx['testng_version']:concerns.append('TestNG_project_native_JUnit4_discovery_unqualified')
 if str(ctx['junit_version']).startswith('5'):concerns.append('JUnit5_project_native_JUnit4_discovery_unqualified')
 if not m['settings'] and j['build_tool']=='maven':concerns.append('Maven_settings_missing')
 rows.append({'sample_index_1based':i,'class_key':j['class_key'],'build_tool':j['build_tool'],'files_materialized':len(files),'excluded_count':len(m['files'])-len(files),'prior_test_sha256':files[prior]['sha256'],'focal_sha256':focal['sha256'],'stale_native_paths':stale,'runtime_config_paths':external_launch,'junit':ctx['junit_version'],'testng':ctx['testng_version'],'concerns':concerns,'benchmark_admitted':False})
from collections import Counter
summary={'n':len(rows),'build_tools':dict(Counter(r['build_tool'] for r in rows)),'concern_counts':dict(Counter(c for r in rows for c in r['concerns'])),'no_flagged_static_concern':sum(not r['concerns'] for r in rows),'source_manifests_verified':len(rows),'context_manifest_sha256':audit.sha(R/'inputs/context251_v1/manifest.json'),'scope':'static readiness only; no automatic skip or terminal failure classification','new_experiment_calls':0}
O=R/'audit/frozen_inputs251_review_v1';O.mkdir(exist_ok=False)
for name,data in [('rows.json',rows),('summary.json',summary)]:
 with (O/name).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
audit.log('B1_FROZEN_INPUTS251_REVIEW',summary=summary,rows_sha256=audit.sha(O/'rows.json'));print(json.dumps(summary,indent=2))

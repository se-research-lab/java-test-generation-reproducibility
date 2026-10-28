"""Back up and finalize the unexecuted new qualifier; static/audit work only."""
import ast,json,sys
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
runner=R/'src/run_gradle_versions_qualification_v1.py'
registry=json.loads((R/'audit/gradle_qualification_sources_v2.json').read_text(encoding='utf-8'))
assert sha(runner)==registry['runner_prepared_not_executed']['sha256']
assert not (R/'validation/gradle_versions_qualification_v1').exists(),'Qualifier must remain unexecuted'
backup=R/'backups/gradle_version_qualifier_pre_final_review_v1.py'
with backup.open('xb') as f:f.write(runner.read_bytes())
assert sha(backup)==sha(runner)
text=runner.read_text(encoding='utf-8')
text=text.replace('import json,msvcrt,os,re,sys,time,shutil','import sys\nsys.dont_write_bytecode=True\nimport json,msvcrt,os,re,time,shutil')
text=text.replace("MANIFEST=CACHE/'recovery_v2/manifest.json'","MANIFEST=CACHE/'recovery_v2/manifest.json'\nFINAL_SOURCE_REGISTRY=R/'audit/gradle_version_qualifier_final_source_registry_v1.json'")
old="ensure(summary['status']=='PASS_METADATA_ONLY' and static['status']=='PASS_STATIC_ONLY','Metadata/static guard prerequisite missing')"
new=old+"\n for p,h in static['code_hashes'].items():ensure(sha(p)==h,'Static-validation code hash drift: '+p)\n source_registry=load(FINAL_SOURCE_REGISTRY)\n for p,h in source_registry['prepared_file_hashes'].items():ensure(sha(p)==h,'Prepared qualifier source hash drift: '+p)"
assert old in text;text=text.replace(old,new)
old="CACHE/'recovery_v2/protocol.json']"
new="CACHE/'recovery_v2/protocol.json',CACHE/'protocol.json',CACHE/'input_stat_manifest.json',FINAL_SOURCE_REGISTRY,JDK/'release']"
assert old in text;text=text.replace(old,new)
old="source=Path(load(CACHE/'protocol.json')['source']);source_after=cache_verify(rows,source);dump(OUT/'source_cache_after.json',source_after)"
new="source=Path(load(CACHE/'protocol.json')['source']);ensure(source==Path('C:/Users/admin/.gradle'),'Unexpected original cache source');source_after=cache_verify(rows,source);dump(OUT/'source_cache_after.json',source_after)"
assert old in text;text=text.replace(old,new)
ast.parse(text);runner.write_text(text,encoding='utf-8')
paths=[runner,R/'src/gradle_command_policy_v2.py',R/'src/gradle_process_supervisor_v2.py',R/'src/validate_gradle_command_policy_v2.py',R/'validation/gradle_command_policy_v2/result.json',R/'src/process_supervisor_v1.py',R/'src/maven_adapter_v1.py',Path(__file__),R/'cache_preparation_gradle_v1/recovery_v2/complete.json',R/'cache_preparation_gradle_v1/recovery_v2/manifest.json',R/'cache_preparation_gradle_v1/recovery_v2/protocol.json',R/'cache_preparation_gradle_v1/protocol.json',R/'inputs/gradle40_context_v2/manifest.json',R/'inputs/gradle40_context_v2/summary.json',R/'manifest300.json',R/'audit/gradle_qualification_sources_v2.json']
record={'scope':'final prepared qualifier/source registry; no runner execution','initial_runner_backup':{'path':str(backup),'sha256':sha(backup)},'prepared_file_hashes':{str(p.resolve()):sha(p) for p in paths},'static_validation':'PASS_STATIC_ONLY,25checks,40contexts,0processes','qualifier_executed':False,'runtime_qualified':False,'Gradle_benchmark_admitted':False,'new_experiment_calls':0}
dump(R/'audit/gradle_version_qualifier_final_source_registry_v1.json',record)
audit.verify();audit.log('B1_GRADLE_VERSION_QUALIFIER_FINAL_SOURCES_PREPARED',registry_sha256=sha(R/'audit/gradle_version_qualifier_final_source_registry_v1.json'),runner_sha256=sha(runner),backup_sha256=sha(backup),new_experiment_calls=0)
print('Final qualifier prepared; static registry pinned; runner NOT executed')

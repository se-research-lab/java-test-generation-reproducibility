"""Preserve v1 export; enrich old command timestamps and V6 POM verification."""
import ast,sys
from maven_adapter_v1 import R,sha
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
source=R/'src/export_policy_attempt_history_v1.py'
target=R/'src/export_policy_attempt_history_v2.py'
text=source.read_text(encoding='utf-8').replace("OUT=R/'policy_attempt_history_v1'","OUT=R/'policy_attempt_history_v2'")
old="e.get('job')==folder.relative_to(B).as_posix()"
assert text.count(old)==1
text=text.replace(old,"str(e.get('job','')).replace('\\\\','/')==folder.relative_to(B).as_posix()")
key="    if result.exists():assert load(result)['source_guard']==load(result)['production_bytecode_guard']=='PASS'"
extra="""
    policy_file=folder/'policy_applied.json'
    if policy_file.exists():
        policy=load(policy_file)
        module=folder/'repo'/by_index[i]['module']
        assert sha(module/'pom.xml')==policy['after_sha256']
        native_policy=load(folder/'native_junit_policy.json')
        before=load(folder/'before_dependency.json')
        if (folder/'after_dependency.json').exists():
            after=load(folder/'after_dependency.json')
            if native_policy['changed']:
                from native_junit_policy_candidate_v1 import compare
                compare(before,after)
            else:
                from maven_adapter_v1 import measurement_policy_bindings
                measurement_policy_bindings(lambda *a,**k:None)['compare_cp'](before,after,policy)
        else:
            assert not policy['changes'] and not native_policy['changed']
"""
assert text.count(key)==1
text=text.replace(key,key+extra)
text=text.replace("'V6_one_measurement_lifecycle_per_class':'PASS'", "'V6_effective_POM_matches_recorded_policy_and_CP_delta_rules':'PASS; conditional changes exist, not an unchanged effective environment','V6_one_measurement_lifecycle_per_class':'PASS'")
ast.parse(text)
with target.open('x',encoding='utf-8') as f:f.write(text)
audit.log('B1_POLICY_HISTORY_V2_PREPARED',source_sha256=sha(target),prior_source_sha256=sha(source),
          reason='Normalize old ledger path separators to recover available timestamps; recheck final V6 POM and classpath delta evidence',
          new_experiment_calls=0,raw_evidence_changes=0)
print('Prepared v2 export; v1 retained; timestamps enriched and conditional-POM checks added; no experiment calls')

"""Read-only API correction in an unadmitted adapter; no corpus changes.
Keep failed fixturev1 and recipev4. Preserve generation/settings/dependencies.
"""
import ast,difflib,json,sys
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

old=R/'src/gradle_native_recipe_v4.py'
new=R/'src/gradle_native_recipe_v5.py'
text=old.read_text(encoding='utf-8')
assert text.count("p.extensions.getByName('sourceSets')")==2
modified=text.replace("p.extensions.getByName('sourceSets')","p.sourceSets")
modified=modified.replace('gradle_native_recipe_v4','gradle_native_recipe_v5')
ast.parse(modified)
with new.open('x',encoding='utf-8') as f:f.write(modified)
diff=R/'audit/gradle_sourceSets_read_api_v2.diff'
with diff.open('x',encoding='utf-8') as f:f.write(''.join(difflib.unified_diff(text.splitlines(True),modified.splitlines(True),fromfile=old.name,tofile=new.name)))
# No other runtime-script/config change beyond object-property access.
assert modified.replace("p.sourceSets","p.extensions.getByName('sourceSets')").replace('gradle_native_recipe_v5','gradle_native_recipe_v4')==text
sources=R/'cache_preparation_gradle_v1/gradle_user_home/wrapper/dists/gradle-2.13-all/1b9wlm73elu4cqnbc0rk7r7qn/gradle-2.13/src/plugins/org/gradle/api/plugins'
convention=sources/'JavaPluginConvention.groovy'
plugin=sources/'JavaPlugin.java'
assert 'SourceSetContainer' in convention.read_text(encoding='utf-8') and 'getSourceSets' in convention.read_text(encoding='utf-8')
assert 'project.getConvention().getPlugin(JavaPluginConvention.class)' in plugin.read_text(encoding='utf-8')
runner=R/'src/run_gradle_native_fixture_v1.py'
runner2=R/'src/run_gradle_native_fixture_v2.py'
rtext=runner.read_text(encoding='utf-8').replace('gradle_native_recipe_v4','gradle_native_recipe_v5').replace('gradle_native_runtime_fixture_v1','gradle_native_runtime_fixture_v2')
ast.parse(rtext)
with runner2.open('x',encoding='utf-8') as f:f.write(rtext)
assert rtext.replace('gradle_native_recipe_v5','gradle_native_recipe_v4').replace('gradle_native_runtime_fixture_v2','gradle_native_runtime_fixture_v1')==runner.read_text(encoding='utf-8')
dump(R/'audit/gradle_sourceSets_read_api_v2.json',{'scope':'synthetic qualification only; unadmitted adapter object lookup correction',
     'old_recipe_sha256':sha(old),'new_recipe_sha256':sha(new),'diff_sha256':sha(diff),
     'old_fixture_runner_sha256':sha(runner),'new_fixture_runner_sha256':sha(runner2),
     'primary_local_sources':[{'path':str(p),'sha256':sha(p)} for p in [convention,plugin]],
     'actual_change':'read p.sourceSets (Gradle Project convention/property lookup) instead of requiring an extension of that name',
     'test_source_edits':0,'dependency_changes':0,'selector_policy_changes':0,'generation_profile_changes':0,
     'corpus_configuration_admitted':False,'new_Java_or_EvoSuite_processes':0,'GPT_API_calls':0,
     'old_failed_evidence_preserved':True})
audit.log('B1_GRADLE_READ_API_QUALIFICATION_V2_PREPARED',recipe_sha256=sha(new),runner_sha256=sha(runner2),
          read_API_change_only=True,corpus_admitted=False,new_experiment_calls=0,GPT_API_calls=0)
print('Prepared recipev5/fixturev2: only read sourceSets API changes; no corpus admission or process launch')

"""Finish the read-API preparation after checking Groovy property evidence.
The first preparation's assertion expected a Java-style getter in Groovy
source; its failure/log and already-written recipe remain preserved.
"""
import ast,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'src/gradle_native_recipe_v4.py';new=R/'src/gradle_native_recipe_v5.py'
assert new.read_text(encoding='utf-8').replace('p.sourceSets',"p.extensions.getByName('sourceSets')").replace('gradle_native_recipe_v5','gradle_native_recipe_v4')==old.read_text(encoding='utf-8')
root=R/'cache_preparation_gradle_v1/gradle_user_home/wrapper/dists/gradle-2.13-all/1b9wlm73elu4cqnbc0rk7r7qn/gradle-2.13/src/plugins/org/gradle/api/plugins'
convention=root/'JavaPluginConvention.groovy';plugin=root/'JavaPlugin.java'
assert 'final SourceSetContainer sourceSets' in convention.read_text(encoding='utf-8')
assert 'project.getConvention().getPlugin(JavaPluginConvention.class)' in plugin.read_text(encoding='utf-8')
assert 'convention.getSourceSets()' in plugin.read_text(encoding='utf-8')
runner=R/'src/run_gradle_native_fixture_v1.py';runner2=R/'src/run_gradle_native_fixture_v2.py'
text=runner.read_text(encoding='utf-8').replace('gradle_native_recipe_v4','gradle_native_recipe_v5').replace('gradle_native_runtime_fixture_v1','gradle_native_runtime_fixture_v2')
ast.parse(text)
with runner2.open('x',encoding='utf-8') as f:f.write(text)
dump(R/'audit/gradle_sourceSets_read_api_v2.json',{'scope':'read-API correction, synthetic qualification only',
     'old_recipe_sha256':sha(old),'new_recipe_sha256':sha(new),'old_runner_sha256':sha(runner),'new_runner_sha256':sha(runner2),
     'diff_sha256':sha(R/'audit/gradle_sourceSets_read_api_v2.diff'),
     'local_primary_sources':[{'path':str(p),'sha256':sha(p)} for p in [convention,plugin]],
     'source_evidence':'Groovy final SourceSetContainer sourceSets property; JavaPlugin obtains it through convention.getSourceSets()',
     'test_source_edits':0,'dependency_policy_changes':0,'selector_policy_changes':0,'generation_profile_changes':0,
     'corpus_configuration_admitted':False,'new_Java_processes':0,'GPT_API_calls':0,
     'old_failed_preparation_and_runtime_fixture_preserved':True})
audit.log('B1_GRADLE_READ_API_FIXTURE_V2_SEALED',recipe_sha256=sha(new),runner_sha256=sha(runner2),
          dependency_changes=0,selector_changes=0,test_source_edits=0,new_experiment_calls=0)
print('PASS preparation: read-API-only change verified from exact Gradle2.13 sources; no corpus/Java execution')

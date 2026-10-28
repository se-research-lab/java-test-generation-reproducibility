"""Correct only the synthetic recipe's read-only PIT engine classpath audit.

The old plugin stores its engine configuration on rootProject.buildscript,
not on the selected project's normal configurations container. Read the
typed PIT task's actual launchClasspath in all three pinned plugin versions.
No provider, dependency, target, generation flag, or native source is changed.
"""
import ast,difflib,subprocess,sys
from pathlib import Path
from maven_adapter_v1 import R,JDK,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
home=R/'cache_preparation_gradle_v1/gradle_user_home/caches/modules-2/files-2.1/info.solidsoft.gradle.pitest/gradle-pitest-plugin'
evidence=R/'audit/gradle_engine_read_api_v3';evidence.mkdir(exist_ok=False)
proof=[]
for version in ['1.3.0','1.4.0','1.15.0']:
 jars=list((home/version).glob('*/*.jar'));assert len(jars)==1
 jar=jars[0]
 result=subprocess.run([str(JDK/'bin/javap.exe'),'-private','-classpath',str(jar),'info.solidsoft.gradle.pitest.PitestTask'],capture_output=True,text=True,check=True)
 assert 'getLaunchClasspath()' in result.stdout and 'FileCollection' in result.stdout
 out=evidence/('PitestTask_'+version+'.txt');out.write_text(result.stdout,encoding='utf-8')
 proof.append({'plugin_version':version,'jar':str(jar),'jar_sha256':sha(jar),'typed_API_evidence':str(out),'evidence_sha256':sha(out)})
old=R/'src/gradle_native_recipe_v5.py';new=R/'src/gradle_native_recipe_v6.py'
text=old.read_text(encoding='utf-8')
before="pit_engine: p.configurations.getByName('pitest')"
after="pit_engine: p.tasks.getByName('pitest').launchClasspath"
assert text.count(before)==1
text=text.replace(before,after).replace('gradle_native_recipe_v5','gradle_native_recipe_v6')
assert text.replace(after,before).replace('gradle_native_recipe_v6','gradle_native_recipe_v5')==old.read_text(encoding='utf-8')
ast.parse(text)
with new.open('x',encoding='utf-8') as f:f.write(text)
diff=evidence/'recipe.diff';diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
runner=R/'src/run_gradle_native_fixture_v2.py';runner3=R/'src/run_gradle_native_fixture_v3.py'
text=runner.read_text(encoding='utf-8').replace('gradle_native_recipe_v5','gradle_native_recipe_v6').replace('gradle_native_runtime_fixture_v2','gradle_native_runtime_fixture_v3')
ast.parse(text)
with runner3.open('x',encoding='utf-8') as f:f.write(text)
dump(evidence/'preparation.json',{'scope':'synthetic qualification read-API correction only','old_recipe_sha256':sha(old),'new_recipe_sha256':sha(new),'old_runner_sha256':sha(runner),'new_runner_sha256':sha(runner3),'diff_sha256':sha(diff),'primary_binary_API_evidence':proof,'reason':'1.3.0 createConfigurations uses rootProject.buildscript.configurations; selected-project ordinary pitest configuration is absent. Typed launchClasspath is the task engine classpath.','test_source_edits':0,'dependency_changes':0,'selector_changes':0,'generation_profile_changes':0,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0,'prior_failures_preserved':True})
audit.log('B1_GRADLE_ENGINE_READ_API_V3_PREPARED',recipe_sha256=sha(new),runner_sha256=sha(runner3),corpus_configuration_admitted=False,new_EvoSuite_calls=0,GPT_API_calls=0)
audit.verify()
print('PASS preparation: typed launchClasspath audit; no experimental configuration changes or corpus calls')

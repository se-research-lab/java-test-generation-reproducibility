"""Supply a repository declaration missing from the synthetic build only.

PIT1.3 resolves the already-pinned engine from root buildscript repositories.
All execution stays offline. Recipe v6 and corpus inputs remain byte-identical.
"""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'src/run_gradle_native_fixture_v3.py';new=R/'src/run_gradle_native_fixture_v4.py'
text=old.read_text(encoding='utf-8')
before='body="apply plugin: \'java\'\\n'
after='body="buildscript { repositories { mavenCentral() } }\\napply plugin: \'java\'\\n'
assert text.count(before)==1;text=text.replace(before,after)
before2="(build/'build.gradle').write_text('// Synthetic root; selected module owns Java/PIT tasks.\\n',encoding='utf-8')"
after2="(build/'build.gradle').write_text('buildscript { repositories { mavenCentral() } }\\n// Synthetic root; selected module owns Java/PIT tasks.\\n',encoding='utf-8')"
assert text.count(before2)==1;text=text.replace(before2,after2).replace('gradle_native_runtime_fixture_v3','gradle_native_runtime_fixture_v4')
ast.parse(text)
with new.open('x',encoding='utf-8') as f:f.write(text)
out=R/'audit/gradle_fixture_tool_repository_v4';out.mkdir(exist_ok=False)
diff=out/'fixture.diff';diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
dump(out/'preparation.json',{'scope':'synthetic build only; offline tool dependency resolution','old_runner_sha256':sha(old),'new_runner_sha256':sha(new),'unchanged_recipe_sha256':sha(R/'src/gradle_native_recipe_v6.py'),'diff_sha256':sha(diff),'previous_failure':'Gradle2.13 PIT1.3.0 launchClasspath resolves through root buildscript repository container, absent in minimal fixture','dependency_versions_changed':False,'production_dependencies_changed':False,'EvoSuite_native_tests_edited':False,'corpus_builds_edited':False,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0})
audit.log('B1_GRADLE_FIXTURE_TOOL_REPOSITORY_V4_PREPARED',runner_sha256=sha(new),recipe_unchanged=True,offline=True,new_EvoSuite_calls=0,GPT_API_calls=0)
print('PASS: synthetic root buildscript repository declaration only; recipe unchanged')

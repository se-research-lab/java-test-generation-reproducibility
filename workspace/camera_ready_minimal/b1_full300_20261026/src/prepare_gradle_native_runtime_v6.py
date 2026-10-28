"""Pre-corpus native-runtime qualification; preserve every earlier candidate.

JDK8 tools bootstrap is exactly the existing E49/Maven runtime environment.
Native Test classpath drops only nonexistent paths (no existing artifact).
These are disclosed harness rules, not assertion/test edits or score retries.
"""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
out=R/'audit/gradle_native_runtime_v6';out.mkdir(exist_ok=False)
changes=[]
def write(old,new,text):
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 diff=out/(new.stem+'.diff');diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 changes.append({'old':str(old),'old_sha256':sha(old),'new':str(new),'new_sha256':sha(new),'diff':str(diff),'diff_sha256':sha(diff)})
old=R/'src/gradle_native_recipe_v6.py';new=R/'src/gradle_native_recipe_v7.py';text=old.read_text(encoding='utf-8')
before='nativeTest.classpath = ss.test.runtimeClasspath';after='nativeTest.classpath = ss.test.runtimeClasspath.filter { File file -> file.exists() } // lazy: after testClasses; preserves all existing artifacts/order'
assert text.count(before)==1;text=text.replace(before,after).replace('gradle_native_recipe_v6','gradle_native_recipe_v7')
text=text.replace("nativeEnabled: nativeTest.enabled,", "nativeRuntimeAbsentPathRule: 'exclude only nonexistent paths, evaluated lazily after testClasses', nativeEnabled: nativeTest.enabled,")
write(old,new,text)
old=R/'src/gradle_process_supervisor_v2.py';new=R/'src/gradle_process_supervisor_v3.py';text=old.read_text(encoding='utf-8')
text=text.replace(" env['JAVA_HOME']=str(JDK);", " env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:\"'+str(JDK/'lib/tools.jar')+'\"'\n env['JAVA_HOME']=str(JDK);")
needle="  for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','JAVA_OPTS','GRADLE_OPTS','GRADLE_HOME','GRADLE_RO_DEP_CACHE']:"
assert text.count(needle)==1
text=text.replace(needle,"  ensure(self.env.get('JAVA_TOOL_OPTIONS')=='-Xbootclasspath/a:\"'+str(JDK/'lib/tools.jar')+'\"','Exact pinned JDK8 tools bootstrap required')\n  ensure(lock.get('code_and_input_hashes',{}).get(str((JDK/'lib/tools.jar').resolve()))==sha(JDK/'lib/tools.jar'),'JDK8 tools JAR must be pinned')\n  for key in ['_JAVA_OPTIONS','JDK_JAVA_OPTIONS','JAVA_OPTS','GRADLE_OPTS','GRADLE_HOME','GRADLE_RO_DEP_CACHE']:")
text=text.replace('B1_gradle_supervisor_v2','B1_gradle_supervisor_v3').replace('gradle_guard_v2','gradle_guard_v3')
write(old,new,text)
old=R/'src/run_gradle_native_fixture_v5.py';new=R/'src/run_gradle_native_fixture_v6.py';text=old.read_text(encoding='utf-8').replace('gradle_process_supervisor_v2','gradle_process_supervisor_v3').replace('B1_gradle_supervisor_v2','B1_gradle_supervisor_v3').replace('gradle_native_recipe_v6','gradle_native_recipe_v7').replace('gradle_native_runtime_fixture_v5','gradle_native_runtime_fixture_v6')
text=text.replace('pinpaths=[Path(__file__),',"pinpaths=[Path(__file__),JDK/'lib/tools.jar',")
text=text.replace("'legacy_absolute_artifact_paths':True,","'legacy_absolute_artifact_paths':True,'JDK8_tools_bootstrap':'exact E49/Maven setting','absent_native_runtime_paths':'excluded lazily only if nonexistent',")
write(old,new,text)
dump(out/'preparation.json',{'scope':'new synthetic runtime qualification, before any Gradle40 experiment','changes':changes,'new_rules':['Native Test runtime classpath lazily excludes only nonexistent entries; existing dependency files and their order retained','Exact E49/Maven JAVA_TOOL_OPTIONS bootstrap of pinned JDK8 tools.jar, inherited by child JVMs'],'reasons':['2.13 synthetic initializationError: AgentLoader rejected nonexistent build/resources/test','8.14.4 synthetic initializationError: WindowsAttachProvider unavailable without tools bootstrap'],'native_Java_edits':0,'generation_flags_changes':0,'dependency_versions_changes':0,'budget_seed_mutator_changes':0,'benchmark_admitted':False,'GPT_API_calls':0,'all_previous_failed_fixtures_preserved':True})
audit.log('B1_GRADLE_NATIVE_RUNTIME_V6_PREPARED',receipt_sha256=sha(out/'preparation.json'),scope='synthetic pre-corpus harness qualification',new_EvoSuite_calls=0,GPT_API_calls=0)
print('PASS preparation; no generated test/production edit; harness differences explicitly recorded')

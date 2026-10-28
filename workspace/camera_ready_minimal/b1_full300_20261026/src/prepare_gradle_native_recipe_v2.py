"""Version the unadmitted pure prototype; no Java/Gradle/test generation."""
import sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/gradle_native_recipe_v1.py';target=R/'src/gradle_native_recipe_v2.py'
text=source.read_text(encoding='utf-8').replace('import copy,hashlib,json,re,sys','import copy,hashlib,json,re,sys,stat')
helper='''
def owned_path(value):
 path=Path(absolute(str(value))).resolve()
 roots=[(R/'jobs').resolve(),(R/'validation').resolve()]
 require(any(path.is_relative_to(root) and path!=root for root in roots),'Recipe path outside owned B1 sandbox')
 cursor=path
 while cursor.is_relative_to(R):
  if cursor.exists() or cursor.is_symlink():
   require(not cursor.is_symlink() and not getattr(cursor.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400),'Recipe reparse/junction path refused')
  if cursor==R:break
  cursor=cursor.parent
 return path.as_posix()

'''
text=text.replace('def relative(value):',helper+'def relative(value):')
text=text.replace("c['repo_root']=absolute(c['repo_root'])","c['repo_root']=owned_path(c['repo_root'])")
text=text.replace("def constants(c,phase_dir):\n selector", "def constants(c,phase_dir):\n phase_dir=Path(owned_path(phase_dir))\n selector")
text=text.replace("def files = collection.files.toList().sort { it.canonicalPath }","def files = collection.files.toList() // retain the Gradle runtime classpath order")
old="    if (dest.parentFile != b1EvidenceDir || !dest.createNewFile()) throw new GradleException('Evidence exists or escapes owned directory')\n    dest.setText(text, 'UTF-8')"
new="""    if (dest.parentFile != b1EvidenceDir) throw new GradleException('Evidence escapes owned directory')
    if (dest.exists()) {
        if (name != 'b1_recipe_configuration.json' || !dest.isFile() || dest.getText('UTF-8') != text) throw new GradleException('Evidence exists or sealed configuration differs')
        return // identical sealed configuration may be read by a later PIT invocation
    }
    if (!dest.createNewFile()) throw new GradleException('Exclusive evidence creation failed')
    dest.setText(text, 'UTF-8')"""
assert old in text;text=text.replace(old,new)
text=text.replace("b1_recipe_runtime_claims.json","b1_recipe_configuration.json").replace("status: 'CANDIDATE_APPLIED_NOT_A_QUALIFICATION_PASS'","status: 'CONFIGURATION_ONLY_NOT_EXECUTION_EVIDENCE', notTaskExecutionEvidence: true")
text=text.replace('gradle_native_recipe_v1','gradle_native_recipe_v2')
text=text.replace("checks=[];artifacts=[]", """checks=[];artifacts=[]
 require('collection.files.toList().sort' not in main_audit_script(config,base/'in_memory/main'),'Classpath order was sorted')
 checks.append('runtime classpath preserves native Gradle iteration order')
 for invalid in ['D:/foreign/repo',str(R/'inputs')]:
  bad=copy.deepcopy(config);bad['repo_root']=invalid
  try:validate_config(bad)
  except RecipeError:pass
  else:raise AssertionError('Unowned source accepted')
 checks.append('source root outside jobs/validation rejected')
 rendered=measurement_script(config,base/'in_memory/measure')
 require(\"name != 'b1_recipe_configuration.json'\" in rendered and \"dest.getText('UTF-8') != text\" in rendered and 'CONFIGURATION_ONLY_NOT_EXECUTION_EVIDENCE' in rendered,'Configuration receipt reuse/label guard missing')
 checks.append('second init load may reuse only identical sealed configuration; runtime evidence still required')""")
compile(text,str(target),'exec')
with target.open('x',encoding='utf-8') as f:f.write(text)
dump(R/'audit/gradle_recipe_v2_changes.json',{'old_source_sha256':sha(source),'new_source_sha256':sha(target),'changes':['bind source/evidence to owned sandbox; reject reparse','idempotent configuration-only receipt; never task-execution evidence','preserve native classpath order'],'runtime_qualified':False,'new_processes':0})
audit.log('B1_GRADLE_RECIPE_V2_PREPARED',source_sha256=sha(target),prior_source_sha256=sha(source),new_experiment_calls=0);print('Prepared pure recipe v2; not runtime qualified')

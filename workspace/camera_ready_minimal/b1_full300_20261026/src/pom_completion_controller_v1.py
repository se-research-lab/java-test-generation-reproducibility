"""E-only Maven lifecycle with source, classpath, bytecode and policy guards.
Import-only execution core. A separate qualified dispatcher must admit each job.
"""
import copy,json,os,shutil,subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
import pandas as pd
from maven_adapter_v1 import R,NS,GuardAbort,sha,dump,generation_bindings,measurement_policy_bindings,native_suite
from pom_namespace_completion_v1 import generation_bindings
from pom_integration_guard_v1 import verify as integration_guard
from measurement_parser_v1 import parse
from native_junit_policy_candidate_v1 import patch as native_junit_patch,compare as native_junit_compare

def ensure(ok,why):
 if not ok:raise GuardAbort(why)
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def source_hashes(root):
 result={}
 for parent,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=[d for d in dirs if d not in {'target','build','.git','.gradle','.evosuite','evosuite-report','evosuite-tests'}]
  for name in files:
   p=Path(parent)/name;ensure(not p.is_symlink(),'Unexpected link in job source');result[p.relative_to(root).as_posix()]=sha(p)
 return result
def bytecode(module):return {p.relative_to(module/'target/classes').as_posix():sha(p) for p in (module/'target/classes').rglob('*.class')}
def cp_entries(path,commands):
 ensure(path.is_file(),'Missing dependency classpath evidence');text=path.read_text(encoding='utf-8').strip();rows=[]
 expected=commands.cache_hashes
 for value in text.split(os.pathsep) if text else []:
  p=Path(value).resolve();ensure(p.is_file(),'Classpath file missing');h=sha(p)
  if p.is_relative_to(commands.cache):
   key=p.relative_to(commands.cache).as_posix();ensure(expected.get(key)==h,'Dependency cache JAR hash changed: '+key)
  else:key=str(p);ensure(commands.lock['tool_hashes'].get(key)==h,'External dependency is not pinned')
  rows.append({'path':key,'absolute_path':str(p),'sha256':h,'bytes':p.stat().st_size})
 return rows
def dependency(commands,args,module,out,label):
 test=out/(label+'_test_classpath.txt');compilecp=out/(label+'_compile_classpath.txt');tree=out/(label+'_tree.txt')
 r=commands.run([*args,'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:tree','org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath','-DoutputFile='+str(tree),'-Dmdep.outputFile='+str(test),'-DincludeScope=test'],cwd=module,timeout=180)
 ensure(r.returncode==0,'Dependency audit unavailable; do not score as benchmark failure')
 r=commands.run([*args,'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath','-Dmdep.outputFile='+str(compilecp),'-DincludeScope=compile'],cwd=module,timeout=180)
 ensure(r.returncode==0,'Production classpath evidence unavailable')
 result={'classpath':cp_entries(test,commands),'compile_classpath':cp_entries(compilecp,commands),'tree_sha256':sha(tree)};dump(out/(label+'_dependency.json'),result);return result
def effective(commands,args,module,out,label):
 p=out/(label+'_effective_pom.xml');r=commands.run([*args,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(p)],cwd=module,timeout=180)
 ensure(r.returncode==0 and p.is_file(),'Effective POM audit unavailable')
 root=ET.parse(p).getroot();plugins=[x for x in root.findall('m:build/m:plugins/m:plugin',NS) if x.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin'];ensure(len(plugins)==1,'Unexpected Surefire shape');return plugins[0]
def archive(out):
 files=[]
 for p in sorted(out.rglob('*')):
  if not p.is_file() or 'temp' in p.relative_to(out).parts or p.name=='artifact_manifest.json':continue
  files.append({'relative':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
 dump(out/'artifact_manifest.json',files)

def execute(out,j,commands,event):
 out=Path(out).resolve();repo=out/'repo';module=repo/j['module'];focal=repo/j['focal_path'];test=j['selected_test_fqcn'];testpath=module/'src/test/java'/Path(*test.split('.')).with_suffix('.java')
 ensure(not (out/'result.json').exists(),'No rerun of a completed job')
 ensure(not list(repo.rglob('target')),'Stale target before controller start')
 before=source_hashes(repo);dump(out/'controller_source_before.json',before)
 expected=dict(before);ns=generation_bindings(commands,out,event);policy_ns=measurement_policy_bindings(event)
 df=pd.DataFrame([{'Project':j['repo_id'],'Module':j['module'],'Focal_Class':j['focal_class'],'Test_Class':test.split('.')[-1],'Focal_Path':str(focal),'Test_Path':testpath.as_posix()}])
 pom=module/'pom.xml';original=pom.read_text(encoding='utf-8');(out/'pom_before_integration.xml').write_text(original,encoding='utf-8')
 ensure(ns['edit_pom_file'](str(module),df,j.get('junit_version') or '4',j.get('testng_version')) is not None,'E49 POM preparation failed')
 ensure(ns['add_evosuite_pom'](str(module)) is not None,'E49 runtime integration failed')
 dump(out/'integration_guard.json',integration_guard(original,pom.read_text(encoding='utf-8')))
 expected[pom.relative_to(repo).as_posix()]=sha(pom)
 ensure(source_hashes(repo)==expected,'Source changed outside module POM during integration')
 generated=ns['run_evosuite_generation_maven'](str(module),str(focal),'Windows',generation_profile='reviewer_assertions')
 native=native_suite(module,test);dump(out/'native_generated.json',json.loads(json.dumps(native,default=str)))
 for row in native['files']:expected[Path(row['path']).relative_to(repo).as_posix()]=row['sha256']
 ensure(source_hashes(repo)==expected,'Generation changed non-native source or introduced unexpected files')
 production=bytecode(module);dump(out/'production_generation_baseline.json',production)
 gate=False;measurement_attempted=False;dep=None;native_junit_added=False
 if generated and native['complete']:
  args=['mvn',*(['-s',str(out/'settings.xml')] if (out/'settings.xml').exists() else []),'-Dtest='+test,*ns['common_maven_skip_args']()]
  beforedep=dependency(commands,args,module,out,'before');beforeeff=effective(commands,args,module,out,'before')
  native_junit_added=native_junit_patch(pom,out,beforedep)
  patch=policy_ns['patch_pom']({**j,'job_index':j['sample_index_1based']},module,out,beforedep,beforeeff)
  expected[pom.relative_to(repo).as_posix()]=sha(pom)
  if patch['changes'] or native_junit_added:
   dep=dependency(commands,args,module,out,'after');aftereff=effective(commands,args,module,out,'after');native_junit_compare(beforedep,dep) if native_junit_added else policy_ns['compare_cp'](beforedep,dep,patch)
   x=copy.deepcopy(beforeeff);y=copy.deepcopy(aftereff)
   if patch['selector_rule_applied']:
    for plugin in [x,y]:
     regular=next(e for e in plugin.findall('m:executions/m:execution',NS) if e.findtext('m:id',namespaces=NS)=='regular-tests');cfg=regular.find('m:configuration',NS);cfg.remove(cfg.find('m:includes',NS))
    regular=next(e for e in aftereff.findall('m:executions/m:execution',NS) if e.findtext('m:id',namespaces=NS)=='regular-tests')
    ensure([v.text for v in regular.findall('m:configuration/m:includes/m:include',NS)]==[test.replace('.','/')+'.java'],'Unexpected effective include')
   ensure(policy_ns['normalize'](x)==policy_ns['normalize'](y),'Effective Surefire outside policy changed')
  else:dep=beforedep
  ensure(source_hashes(repo)==expected,'Dependency/policy audit changed source outside allowed POM')
  ensure(not list((module/'target/surefire-reports').glob('TEST-*.xml')) and not (module/'target/pit-reports/mutations.csv').exists(),'Stale measurement evidence before lifecycle')
  measurement_attempted=True;gate=ns['run_maven_test_command'](str(module),df,'Windows')[0]
  if dep:
   for row in dep['classpath']+dep['compile_classpath']:ensure(sha(row['absolute_path'])==row['sha256'],'Classpath JAR changed during measurement')
 ensure(source_hashes(repo)==expected,'Source/native test changed during measurement')
 observed=bytecode(module);changed=[p for p in production.keys()&observed.keys() if production[p]!=observed[p]];added=sorted(observed.keys()-production.keys());missing=sorted(production.keys()-observed.keys())
 ensure(not changed and not added,'Production bytecode changed/added');ensure(not gate or not missing,'Build gate true with missing production classes')
 dump(out/'production_bytecode_guard.json',{'changed':changed,'added':added,'missing':missing,'baseline_available':bool(production)})
 raw=parse(module,j['focal_class'],j['package'],test,gate)
 result={'sample_index_1based':j['sample_index_1based'],'class_key':j['class_key'],'repo_id':j['repo_id'],'seed':j['seed'],'configuration':'E1_Maven_native_JUnit_amendment_v2','native_junit_added':native_junit_added,'generation_success':bool(generated),'generation_calls':commands.generations,'measurement_attempted':measurement_attempted,'GPT_API_calls':0,'source_guard':'PASS','production_bytecode_guard':'PASS','terminal':True,**raw}
 dump(out/'result.json',result);event('JOB_TERMINAL',class_key=j['class_key'],result_sha256=sha(out/'result.json'));archive(out);return result

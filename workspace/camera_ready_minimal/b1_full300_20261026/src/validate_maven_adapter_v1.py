"""Pure contract/policy fixtures; deliberately no Java, Maven, PIT or API calls."""
import copy,json,subprocess,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import maven_adapter_v1 as a
R=Path(__file__).resolve().parents[1];O=R/'validation/maven_adapter_v1';O.mkdir(parents=True,exist_ok=False)
checks=[]
def reject(name,fn,exc=a.GuardAbort):
 try:fn()
 except exc:checks.append(name)
 else:raise AssertionError('Expected rejection: '+name)
job={'sample_index_1based':3,'seed':20261026,'build_tool':'maven','focal_path':'src/main/java/fixture/BranchFixture.java','reused_result':{}}
argv=[str(a.JDK/'bin/java.exe'),'-jar',str(a.WORKSPACE/'scripts_v2/evosuite-1.2.0.jar'),'-class','fixture.BranchFixture','-projectCP',str(O/'repo/target/classes'),'-Dtest_dir='+str(O/'repo/src/test/java'),'-Dreport_dir='+str(O/'repo/evosuite-report'),*a.reviewer_options()]
accepted=a.checked_generation_argv(argv,job,O);assert accepted[-2:]==['-seed','20261026'];checks.append('original_index_seed_and_exact_E49_options')
for name,change in [('accepted49',{'reused_result':{'already':True}}),('wrong_seed',{'seed':7}),('Gradle_rejected_by_Maven',{'build_tool':'gradle'})]:reject(name,lambda change=change:a.checked_generation_argv(argv,{**job,**change},O))
for flag in ['-Dassertions=false','-Dsearch_budget=120','-seed=123','-generateSuite','-Dfoo=true']:
 reject('reject_'+flag,lambda flag=flag:a.checked_generation_argv(argv+[flag],job,O))
bad=argv.copy();bad[bad.index('-jar')+1]='wrong.jar';reject('wrong_tool',lambda:a.checked_generation_argv(bad,job,O))
badout=[('-Dtest_dir='+str(R.parent)) if s.startswith('-Dtest_dir=') else s for s in argv];reject('output_escape',lambda:a.checked_generation_argv(badout,job,O))
reject('job_outside_B1',lambda:a.checked_generation_argv(argv,job,R.parent))
reject('backup_not_job',lambda:a.checked_generation_argv(argv,job,R/'backups'))
def broad_handler():
 try:a.checked_generation_argv(argv+['-Dassertions=false'],job,O)
 except Exception:raise AssertionError('Guard was swallowed by legacy handler')
reject('guard_bypasses_legacy_broad_exception',broad_handler)
module=O/'native';folder=module/'src/test/java/fixture';folder.mkdir(parents=True)
for name in ['BranchFixture_ESTest.java','BranchFixture_ESTest_scaffolding.java','SomeFilesTest.java']:(folder/name).write_text('// synthetic only\n',encoding='utf-8')
suite=a.native_suite(module,'fixture.BranchFixture_ESTest');assert suite['complete'] and len(suite['files'])==2;checks.append('native_exact_pair_ignores_FilesTest')
wrong=O/'wrong_case/src/test/java/fixture';wrong.mkdir(parents=True);(wrong/'BranchFixture_estest.java').write_text('// synthetic',encoding='utf-8')
assert not a.native_suite(O/'wrong_case','fixture.BranchFixture_ESTest')['complete'];checks.append('native_case_sensitive_on_Windows')

events=[];policy=a.measurement_policy_bindings(lambda kind,**kw:events.append({'kind':kind,**kw}))
def jar(path,names):
 path.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(path,'x') as z:
  for n in names:z.writestr(n,b'SYNTHETIC_NAME_ONLY_NOT_BYTECODE')
 return {'path':path.relative_to(O/'cache').as_posix(),'absolute_path':str(path),'sha256':a.sha(path),'bytes':path.stat().st_size}
jold=jar(O/'cache/junit/junit/4.8.1/junit-4.8.1.jar',['org/junit/Test.class'])
jnew=jar(O/'cache/junit/junit/4.13.2/junit-4.13.2.jar',['org/junit/Test.class','org/junit/rules/TestRule.class'])
ham=jar(O/'cache/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar',['org/hamcrest/Matcher.class'])
pom='<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><dependencies><dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.8.1</version><scope>test</scope></dependency></dependencies><build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>2.17</version></plugin></plugins></build></project>'
effective=ET.fromstring('<plugin xmlns="http://maven.apache.org/POM/4.0.0"><version>2.17</version><executions><execution><id>default-test</id></execution><execution><id>regular-tests</id><configuration><includes><include>/fixture/BranchFixture_ESTest.java</include></includes></configuration></execution></executions></plugin>')
out=O/'policy_both';m=out/'repo';m.mkdir(parents=True);(m/'pom.xml').write_text(pom,encoding='utf-8')
before={'classpath':[jold],'compile_classpath':[]};j={'job_index':3,'selected_test_fqcn':'fixture.BranchFixture_ESTest'}
p=policy['patch_pom'](j,m,out,before,effective);assert p['JUnit_rule_applied'] and p['selector_rule_applied'] and p['only_allowlisted_semantic_changes'];checks.append('E49_conditional_JUnit_and_relative_selector')
after={'classpath':[jnew,ham],'compile_classpath':[]};policy['compare_cp'](before,after,p);checks.append('allow_only_declared_test_JUnit_Hamcrest_delta')
reject('production_CP_drift',lambda:policy['compare_cp'](before,{**after,'compile_classpath':[jnew]},p),AssertionError)
out2=O/'unsafe_scope';m2=out2/'repo';m2.mkdir(parents=True);(m2/'pom.xml').write_text(pom.replace('<scope>test</scope>','<scope>compile</scope>'),encoding='utf-8')
reject('JUnit_compile_scope_override_rejected',lambda:policy['patch_pom'](j,m2,out2,before,effective),AssertionError)
out3=O/'already_modern';m3=out3/'repo';m3.mkdir(parents=True);(m3/'pom.xml').write_text(pom.replace('4.8.1','4.13.2'),encoding='utf-8')
simple=ET.fromstring('<plugin xmlns="http://maven.apache.org/POM/4.0.0"><version>2.17</version></plugin>')
unchanged=policy['patch_pom'](j,m3,out3,after,simple);assert unchanged['changes']==[];checks.append('no_unnecessary_patch')
# Loading extraction bodies binds names, but does not import shared runner or invoke commands.
class NoCommands:
 TimeoutExpired=subprocess.TimeoutExpired
 def run(self,*args,**kw):raise a.GuardAbort('No subprocess allowed in pure contract test')
 def check_call(self,*args,**kw):raise a.GuardAbort('No subprocess allowed in pure contract test')
ns=a.generation_bindings(NoCommands(),O,lambda *args,**kw:None)
assert 'run_evosuite_generation_maven' in ns;checks.append('generation_namespace_loads_without_process_or_GPT_import')
report={'status':'PASS','checks':checks,'count':len(checks),'adapter_sha256':a.sha(R/'src/maven_adapter_v1.py'),'fixture_kind':'pure argv/XML/JAR-entry-name contracts, not executed Java or Maven integration','Java_calls':0,'GPT_API_calls':0,'benchmark_admitted':False,'remaining':'actual runtime fixture; cache isolation; evaluator/parser audit; stop/recovery supervisor; Gradle adapter'}
a.dump(O/'result.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))

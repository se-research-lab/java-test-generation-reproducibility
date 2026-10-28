"""One synthetic Java fixture. No benchmark class selection, no automatic retry."""
import json,sys
from pathlib import Path
import pandas as pd
import maven_adapter_v1 as a
from maven_fixture_commands_v1 import FixtureCommands
from pom_integration_guard_v1 import verify as verify_pom
from measurement_parser_v1 import parse
R=a.R;B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
CACHE=R/'cache_preparation_v1/maven_cache'
assert load(R/'cache_preparation_v1/complete.json')['status']=='PASS','Private cache not complete'
for fixture in ['maven_adapter_v1','process_supervisor_v1','pom_integration_guard_v1']:assert load(R/'validation'/fixture/'result.json')['status']=='PASS'
O=R/'validation/maven_runtime_fixture_v1';O.mkdir(parents=True,exist_ok=False);M=O/'repo';(M/'src/main/java/fixture').mkdir(parents=True)
FOCAL=M/'src/main/java/fixture/BranchFixture.java';FOCAL.write_text('package fixture; public class BranchFixture { public int classify(int n) { if(n<0) return -1; if(n==0) return 0; return n+1; } }\n',encoding='utf-8')
POM=M/'pom.xml';POM.write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>local.b1</groupId><artifactId>synthetic-fixture</artifactId><version>1</version><properties><maven.compiler.source>1.8</maven.compiler.source><maven.compiler.target>1.8</maven.compiler.target><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><dependencies><dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.13.2</version><scope>test</scope></dependency></dependencies><build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.1</version></plugin></plugins></build></project>',encoding='utf-8')
(O/'settings.xml').write_text('<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"><offline>true</offline></settings>',encoding='utf-8')
code=[Path(__file__),R/'src/maven_adapter_v1.py',R/'src/process_supervisor_v1.py',R/'src/maven_fixture_commands_v1.py',R/'src/pom_integration_guard_v1.py',R/'src/measurement_parser_v1.py',FOCAL,O/'settings.xml']
toolpaths=[a.JDK/'bin/java.exe',a.MVN,a.WORKSPACE/'scripts_v2/evosuite-1.2.0.jar',a.WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar',a.JDK/'lib/tools.jar']
lock={'code_and_input_hashes':{str(p.resolve()):a.sha(p) for p in code},'tools':{str(p.resolve()):a.sha(p) for p in toolpaths},'cache':str(CACHE),'benchmark_admitted':False,'scope':'one synthetic fixture only','seed':20261023}
a.dump(O/'fixture_lock.json',lock)
def event(kind,**kw):
 with (O/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'kind':kind,**kw},ensure_ascii=False)+'\n')
 audit.log('B1_SYNTHETIC_'+kind,**kw)
commands=FixtureCommands(O,CACHE,event);ns=a.generation_bindings(commands,O,event);test='fixture.BranchFixture_ESTest';testpath=M/'src/test/java/fixture/BranchFixture_ESTest.java'
df=pd.DataFrame([{'Project':'synthetic','Module':'','Focal_Class':'BranchFixture','Test_Class':'BranchFixture_ESTest','Focal_Path':str(FOCAL),'Test_Path':testpath.as_posix()}])
before=POM.read_text(encoding='utf-8');(O/'pom_before.xml').write_text(before,encoding='utf-8')
assert ns['edit_pom_file'](str(M),df,'4.13.2',None) is not None
assert ns['add_evosuite_pom'](str(M)) is not None
a.dump(O/'pom_integration_guard.json',verify_pom(before,POM.read_text(encoding='utf-8')))
event('FIXTURE_BEGIN',lock_sha256=a.sha(O/'fixture_lock.json'),benchmark=False)
try:
 generated=ns['run_evosuite_generation_maven'](str(M),str(FOCAL),'Windows',generation_profile='reviewer_assertions')
 native=a.native_suite(M,test);a.dump(O/'native_before_measurement.json',native)
 if not generated or not native['complete']:raise RuntimeError('Synthetic generation/scaffold failed; no benchmark admission')
 baseline={p.relative_to(M/'target/classes').as_posix():a.sha(p) for p in (M/'target/classes').rglob('*.class')};a.dump(O/'production_baseline.json',baseline)
 gate=ns['run_maven_test_command'](str(M),df,'Windows')[0]
 observed={p.relative_to(M/'target/classes').as_posix():a.sha(p) for p in (M/'target/classes').rglob('*.class')}
 assert baseline==observed,'Production bytecode changed across full lifecycle'
 assert a.native_suite(M,test)['files']==native['files'],'Native source changed'
 evidence=parse(M,'BranchFixture','fixture',test,gate);a.dump(O/'evidence.json',evidence)
 assert evidence['strict_measurement_evidence'],'Synthetic full lifecycle evidence incomplete'
 result={'status':'PASS','generation_calls':commands.generations,'strict_measurement_evidence':True,'score':evidence['legacy_strict_mutation_percent'],'mutants':evidence['focal_mutants'],'generated_source_unchanged':True,'production_bytecode_unchanged':True,'benchmark_admitted':False,'GPT_API_calls':0,'limitation':'synthetic integration only; not full300 admission'}
 a.dump(O/'result.json',result);event('FIXTURE_COMPLETE',**result);print(json.dumps(result,indent=2))
except BaseException as ex:
 a.dump(O/'failure.json',{'error_type':type(ex).__name__,'detail':str(ex),'generation_calls':commands.generations,'benchmark_admitted':False,'auto_retry':False});event('FIXTURE_FAILED',error_type=type(ex).__name__,detail=str(ex));raise

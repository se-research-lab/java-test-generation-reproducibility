"""Saved synthetic suite only; test POM serializer or test-only JUnit3 support."""
import argparse,copy,json,msvcrt,shutil,sys,traceback
from pathlib import Path
import pandas as pd
from maven_adapter_v1 import R,JDK,MVN,sha,dump,generation_bindings as base_bindings
from pom_namespace_completion_v1 import generation_bindings as pom_bindings
from junit3_test_support_completion_v1 import patch as junit_patch
from completion_measurement_commands_v1 import MeasurementCommands
from maven_controller_v2 import dependency,effective,bytecode,archive,source_hashes
from pom_integration_guard_v1 import verify
from measurement_parser_v1 import parse
from run_maven_b1_v3 import guards
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def execute(kind):
 out=R/'validation'/('completion_maven_'+kind+'_v2');out.mkdir(exist_ok=False);m=out/'repo';m.mkdir()
 saved=R/'validation/long_classpath_fixture_v1/repo'
 for rel in ['src/main/java/fixture/BranchFixture.java','src/test/java/fixture/BranchFixture_ESTest.java','src/test/java/fixture/BranchFixture_ESTest_scaffolding.java']:
  src=saved/rel;dest=m/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);assert sha(src)==sha(dest)
 text=(R/'validation/maven_runtime_fixture_v1/pom_before.xml').read_text()
 if kind=='pom':
  text=text.replace('http://maven.apache.org/POM/4.0.0','https://maven.apache.org/POM/4.0.0').replace('<project ','<project xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd" ',1)
 else:
  text=text.replace('<version>4.13.2</version><scope>test</scope>','<version>3.8.1</version><scope>compile</scope>').replace('<version>3.1</version>','<version>3.8.0</version>')
  text=text.replace('</dependencies>','<dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter-api</artifactId><version>5.6.0</version><scope>test</scope></dependency><dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter-engine</artifactId><version>5.6.0</version><scope>test</scope></dependency></dependencies>')
 (m/'pom.xml').write_text(text,encoding='utf-8');(out/'initial_pom.xml').write_text(text,encoding='utf-8')
 job={'sample_index_1based':0,'class_key':'synthetic:fixture.BranchFixture','seed':20261023,'repo_id':'synthetic','module':'','build_tool':'maven','focal_path':'src/main/java/fixture/BranchFixture.java','focal_class':'BranchFixture','selected_test_fqcn':'fixture.BranchFixture_ESTest','package':'fixture','reused_result':{}}
 def event(kind,**kw):
  with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'kind':kind,**kw})+'\n')
  audit.log('COMPLETION_MAVEN_FIXTURE_'+kind,fixture=str(out),**kw)
 sources=source_hashes(m)
 pins=load(R/'admission_maven_v6.json')['code_and_input_hashes'].copy()
 codes=[Path(__file__),R/'src/pom_namespace_completion_v1.py',R/'src/junit3_test_support_completion_v1.py',R/'src/completion_measurement_commands_v1.py']
 pins.update({str(p.resolve()):sha(p) for p in codes})
 admission={'scope':'synthetic_measurement_qualification','output':str(out.resolve()),'job':job,'generation_allowed':False,'GPT_generation_authorized':False,'code_and_input_hashes':pins,'tool_hashes':{str(p.resolve()):sha(p) for p in [MVN,JDK/'bin/java.exe',JDK/'lib/tools.jar',R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']}}
 dump(out/'admission.json',admission);commands=MeasurementCommands(out,job,out/'admission.json',event)
 ns=(pom_bindings if kind=='pom' else base_bindings)(commands,out,event)
 df=pd.DataFrame([{'Project':'synthetic','Module':'','Focal_Class':'BranchFixture','Test_Class':'BranchFixture_ESTest','Focal_Path':str(m/job['focal_path']),'Test_Path':(m/'src/test/java/fixture/BranchFixture_ESTest.java').as_posix()}])
 try:
  assert ns['edit_pom_file'](str(m),df,'5' if kind=='junit3' else '4',None) is not None
  assert ns['add_evosuite_pom'](str(m)) is not None
  dump(out/'integration_guard.json',verify(text,(m/'pom.xml').read_text()))
  args=['mvn','-Dtest='+job['selected_test_fqcn'],*ns['common_maven_skip_args']()]
  r=commands.run(['mvn',*ns['common_maven_skip_args'](),'-DskipTests=true','compile','dependency:build-classpath','-Dmdep.outputFile='+str(m/'target/evosuite-classpath.txt')],cwd=m,timeout=300);assert r.returncode==0,'Fixture production compilation failed'
  baseline=bytecode(m);assert baseline;dump(out/'production_baseline.json',baseline)
  before=dependency(commands,args,m,out,'before');effective(commands,args,m,out,'before')
  if kind=='junit3':
   junit_patch(m,out,before)
   after=dependency(commands,args,m,out,'after');effective(commands,args,m,out,'after')
   assert before['classpath']==after['classpath'] and before['compile_classpath']==after['compile_classpath'],'Dependency graph changed'
  expected=source_hashes(m);gate=ns['run_maven_test_command'](str(m),df,'Windows')[0]
  assert expected==source_hashes(m) and baseline==bytecode(m),'Source/production bytecode changed'
  raw=parse(m,'BranchFixture','fixture',job['selected_test_fqcn'],gate);dump(out/'evidence.json',raw)
  assert raw['strict_measurement_evidence'] and raw['killed_mutants']>0,'Synthetic measurement/provider positive control failed'
  for rel,h in sources.items():
   if rel!='pom.xml':assert sha(m/rel)==h
  dump(out/'result.json',{'status':'PASS_SYNTHETIC_ONLY','kind':kind,'production_bytecode_unchanged':True,'native_suite_unchanged':True,'generation_calls':0,'GPT_API_calls':0,'score':raw['mutation_score_percent'],'mutants':raw['focal_mutants'],'production_dependency_graph_unchanged':True,'source_code_sha256':sha(__file__)})
  archive(out);print('PASS',kind,flush=True)
 except BaseException as e:
  dump(out/'failure.json',{'error':str(e),'traceback':traceback.format_exc(),'new_generation_calls':0,'automatic_retry':False});archive(out);raise
def main():
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=['pom','junit3'],required=True);a=p.parse_args()
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:guards(load(R/'admission_maven_v6.json'));execute(a.kind)
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()

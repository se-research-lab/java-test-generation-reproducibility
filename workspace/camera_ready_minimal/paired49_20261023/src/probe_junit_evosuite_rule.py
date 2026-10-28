"""Mechanistic runtime API probe only; no CUT, test generation, or PIT measurement."""
import json,os,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
out=BASE/'validation/junit_rule_probe_v1';out.mkdir(exist_ok=False)
java=Path('C:/Program Files/Java/jdk1.8.0_172/bin/java.exe');javac=java.with_name('javac.exe')
runtime=audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
cache=audit.ROOT/'camera_ready_minimal/maven_cache_20261023/junit/junit'
source=out/'EvoSuiteRuleProbe.java'
source.write_text('public class EvoSuiteRuleProbe { public static void main(String[] args) throws Exception { Class<?> c = Class.forName("org.evosuite.runtime.vnet.NonFunctionalRequirementRule"); System.out.println("LOADED " + c.getName()); } }',encoding='utf-8')
classes=out/'classes';classes.mkdir()
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS']:env.pop(key,None)
def command(name,argv):
    r=subprocess.run(list(map(str,argv)),cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=20)
    stdout=out/(name+'.stdout.txt');stderr=out/(name+'.stderr.txt')
    stdout.write_text(r.stdout,encoding='utf-8');stderr.write_text(r.stderr,encoding='utf-8')
    row={'argv':list(map(str,argv)),'returncode':r.returncode,'stdout':stdout.name,'stderr':stderr.name,'stdout_sha256':audit.sha(stdout),'stderr_sha256':audit.sha(stderr)}
    with (out/(name+'.json')).open('x',encoding='utf-8') as f:json.dump(row,f,indent=2)
    audit.log('JUNIT_API_PROBE_COMMAND',name=name,**row)
    return r
assert command('compile',[javac,'-d',classes,source]).returncode==0
results=[]
for version in ['4.8','4.8.2','4.13.2']:
    jar=cache/version/('junit-'+version+'.jar');h=audit.sha(jar)
    result=command('junit_'+version.replace('.','_'),[java,'-cp',os.pathsep.join(map(str,[classes,runtime,jar])),'EvoSuiteRuleProbe'])
    expected=version=='4.13.2'
    assert (result.returncode==0)==expected
    if not expected:assert 'org/junit/rules/TestRule' in result.stderr
    assert audit.sha(jar)==h
    results.append({'junit_version':version,'jar_sha256':h,'returncode':result.returncode,'rule_loads':result.returncode==0})
report={'status':'PASS','purpose':'isolate TestRule API linkage; no claim of passing benchmark suites','results':results,
    'runtime_sha256':audit.sha(runtime),'java_sha256':audit.sha(java),'javac_sha256':audit.sha(javac),
    'benchmark_jobs':0,'generation_calls':0,'GPT_calls':0,'original_dependencies_or_configuration_modified':False}
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('JUNIT_API_PROBE_COMPLETE',status='PASS',summary_sha256=audit.sha(out/'summary.json'),benchmark_jobs=0)
print(json.dumps(report))

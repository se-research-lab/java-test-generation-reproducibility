"""E-only synthetic fixture: actual Java generation and JUnit runtime, no benchmark/API."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
STAGE=BASE/'evo_patch'
sys.path.insert(0,str(BASE))
import audit
sys.path.insert(0,str(STAGE/'working/AgoneTest'))
from evosuite_profile import REVIEWER,maven_generation_options


def main():
    work=STAGE/'fixtures/assertions_runtime_01';work.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172')
    java=jdk/'bin/java.exe';javac=jdk/'bin/javac.exe'
    tools={
        'evosuite':audit.ROOT/'scripts_v2/evosuite-1.2.0.jar',
        'runtime':audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar',
        'junit':Path('C:/Users/admin/.m2/repository/junit/junit/4.13.2/junit-4.13.2.jar'),
        'hamcrest':Path('C:/Users/admin/.m2/repository/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar')}
    fingerprints={str(p):audit.sha(p) for p in [java,javac,*tools.values()]}
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
    env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env.get('PATH','')
    commands=[]
    def run(name,argv,timeout=60,expected=0):
        command=[str(x) for x in argv]
        audit.log('FIXTURE_COMMAND_START',fixture='synthetic_not_benchmark',name=name,argv=command,cwd=str(work),timeout=timeout)
        started=time.monotonic()
        try:
            result=subprocess.run(command,cwd=work,env=env,capture_output=True,text=True,errors='replace',timeout=timeout)
            rc=result.returncode;stdout=result.stdout;stderr=result.stderr
        except subprocess.TimeoutExpired as exc:
            rc=-999
            stdout=exc.stdout or '';stderr=exc.stderr or ''
            if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
        out=work/(name+'.stdout.txt');err=work/(name+'.stderr.txt')
        out.write_text(stdout,encoding='utf-8');err.write_text(stderr,encoding='utf-8')
        record={'name':name,'argv':command,'returncode':rc,'expected_returncode':expected,'duration_seconds':time.monotonic()-started,
                'stdout':str(out.relative_to(BASE)),'stderr':str(err.relative_to(BASE)),
                'stdout_sha256':audit.sha(out),'stderr_sha256':audit.sha(err)}
        commands.append(record);audit.log('FIXTURE_COMMAND_END',**record)
        (work/'command_manifest.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
        assert rc==expected, f'{name} returned {rc}; see preserved logs'
        return stdout+stderr
    for folder in ['src/fixture','classes','generated','reports','testclasses','negative/fixture']:(work/folder).mkdir(parents=True)
    cut=work/'src/fixture/BranchFixture.java'
    cut.write_text('package fixture;\npublic class BranchFixture {\n'
                   '  public int bounded(int x) { if (x < 0) return -1; if (x > 10) return 10; return x; }\n'
                   '  public boolean even(int x) { return x % 2 == 0; }\n}\n',encoding='utf-8')
    audit.log('FIXTURE_SOURCE_CREATED',path=str(cut.relative_to(BASE)),sha256=audit.sha(cut),role='synthetic control, not study class')
    run('java_version',[java,'-version'])
    run('compile_cut',[javac,'-source','8','-target','8','-d',work/'classes',cut])
    run('generate',[java,'-jar',tools['evosuite'],'-class','fixture.BranchFixture','-projectCP',work/'classes',
                    '-Dtest_dir='+str(work/'generated'),'-Dreport_dir='+str(work/'reports'),
                    *maven_generation_options(REVIEWER),'-seed','20261023'],timeout=240)
    generated=sorted((work/'generated').rglob('*.java'))
    assert any(p.name=='BranchFixture_ESTest.java' for p in generated)
    assert any(p.name=='BranchFixture_ESTest_scaffolding.java' for p in generated)
    generated_hashes={str(p.relative_to(work)):audit.sha(p) for p in generated}
    test=next(p for p in generated if p.name=='BranchFixture_ESTest.java')
    text=test.read_text(encoding='utf-8')
    assert 'assert' in text and 'extends BranchFixture_ESTest_scaffolding' in text
    cp=os.pathsep.join(str(p) for p in [work/'classes',tools['runtime'],tools['junit'],tools['hamcrest']])
    run('compile_tests',[javac,'-source','8','-target','8','-cp',cp,'-d',work/'testclasses',*generated])
    fullcp=str(work/'testclasses')+os.pathsep+cp
    success=run('junit_generated',[java,'-javaagent:'+str(tools['runtime']),'-cp',fullcp,
                                 'org.junit.runner.JUnitCore','fixture.BranchFixture_ESTest'])
    assert 'OK (' in success
    failing=work/'negative/fixture/IntentionalFailure.java'
    failing.write_text('package fixture; public class IntentionalFailure { @org.junit.Test public void fails() { org.junit.Assert.fail("negative control"); } }',encoding='utf-8')
    run('compile_negative',[javac,'-cp',cp,'-d',work/'testclasses',failing])
    negative=run('junit_negative',[java,'-cp',fullcp,'org.junit.runner.JUnitCore','fixture.IntentionalFailure'],expected=1)
    assert 'FAILURES!!!' in negative
    # Removing scaffold must fail compilation, without editing any generated byte.
    (work/'without_scaffold').mkdir()
    run('missing_scaffold',[javac,'-cp',cp,'-d',work/'without_scaffold',test],expected=1)
    assert generated_hashes=={str(p.relative_to(work)):audit.sha(p) for p in generated}
    assert fingerprints=={str(p):audit.sha(p) for p in [java,javac,*tools.values()]}
    report={'status':'PASS','fixture':'synthetic BranchFixture only','profile':REVIEWER,
            'generated_test_and_scaffold':generated_hashes,'tool_hashes':fingerprints,
            'jdk':'1.8.0_172','search_budget_seconds':60,'seed':20261023,
            'actual_generated_tests_pass':True,'negative_test_detected':True,'missing_scaffold_rejected':True,
            'generated_bytes_modified':False,'api_calls':0,'benchmark_classes_generated':0,
            'maven_jacoco_pit_integration_validated':False,
            'limitations':'Direct CLI + javac/JUnit fixture; not full native Maven pipeline; no throughput or study efficacy claim'}
    (STAGE/'reports/fixture_result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    audit.log('SYNTHETIC_FIXTURE_COMPLETE',status='PASS',report='evo_patch/reports/fixture_result.json',
              sha256=audit.sha(STAGE/'reports/fixture_result.json'))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

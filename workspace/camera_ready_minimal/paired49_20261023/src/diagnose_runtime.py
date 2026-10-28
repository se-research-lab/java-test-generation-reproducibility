"""Retry runtime on the exact generated fixture bytes, adding JDK8 tools.jar only."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import audit


def main():
    stage=BASE/'evo_patch';work=stage/'fixtures/assertions_runtime_01'
    out=stage/'fixtures/runtime_toolsjar_02';out.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172')
    tools=jdk/'lib/tools.jar'
    paths=[work/'testclasses',work/'classes',audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar',
           Path('C:/Users/admin/.m2/repository/junit/junit/4.13.2/junit-4.13.2.jar'),
           Path('C:/Users/admin/.m2/repository/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'),tools]
    sources=sorted((work/'generated').rglob('*.java'))
    before={str(p):audit.sha(p) for p in sources}
    argv=[str(jdk/'bin/java.exe'),'-javaagent:'+str(paths[2]),'-cp',os.pathsep.join(map(str,paths)),
          'org.junit.runner.JUnitCore','fixture.BranchFixture_ESTest']
    env=dict(os.environ);env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env['PATH']
    audit.log('FIXTURE_DIAGNOSTIC_START',reason='Attach provider failure; test adding tools.jar already used by legacy E POM',
              argv=argv,generated_hashes=before,tools_jar_sha256=audit.sha(tools))
    result=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=60)
    for label,text in [('stdout',result.stdout),('stderr',result.stderr)]:
        (out/(label+'.txt')).write_text(text,encoding='utf-8')
    assert before=={str(p):audit.sha(p) for p in sources}
    record={'returncode':result.returncode,'generated_bytes_unchanged':True,
            'passed':'OK (' in result.stdout and result.returncode==0,'argv':argv,
            'scope':'one synthetic runtime diagnostic only; no benchmark changes'}
    (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    audit.log('FIXTURE_DIAGNOSTIC_END',**record,stdout_sha256=audit.sha(out/'stdout.txt'),stderr_sha256=audit.sha(out/'stderr.txt'))
    print(json.dumps(record,indent=2));print(result.stdout);print(result.stderr)


if __name__=='__main__':main()

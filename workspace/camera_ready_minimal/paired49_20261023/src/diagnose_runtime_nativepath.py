"""Control native library resolution for the existing fixture; no test or JDK edits."""
import json,os,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit


def main():
    stage=BASE/'evo_patch';fixture=stage/'fixtures/assertions_runtime_01'
    out=stage/'fixtures/runtime_nativepath_04';out.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172');runtime=audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
    cp=os.pathsep.join(map(str,[fixture/'testclasses',fixture/'classes',runtime,
        Path('C:/Users/admin/.m2/repository/junit/junit/4.13.2/junit-4.13.2.jar'),
        Path('C:/Users/admin/.m2/repository/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'),jdk/'lib/tools.jar']))
    inputs={str(p):audit.sha(p) for p in (fixture/'generated').rglob('*.java')}
    env=dict(os.environ);env['JAVA_HOME']=str(jdk)
    env['PATH']=str(jdk/'jre/bin')+os.pathsep+str(jdk/'bin')+os.pathsep+env['PATH']
    results=[]
    for name,agent in [('nativepath_agent',True),('nativepath_dynamic',False)]:
        argv=[str(jdk/'bin/java.exe'),'-Djava.library.path='+str(jdk/'jre/bin')]
        if agent:argv+=['-javaagent:'+str(runtime)]
        argv+=['-cp',cp,'org.junit.runner.JUnitCore','fixture.BranchFixture_ESTest']
        audit.log('NATIVE_PATH_CONTROL_START',name=name,argv=argv,scope='E synthetic fixture process only')
        r=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=60)
        for label,text in [('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+label+'.txt')).write_text(text,encoding='utf-8')
        rec={'name':name,'returncode':r.returncode,'pass':r.returncode==0 and 'OK (' in r.stdout,'argv':argv}
        results.append(rec);audit.log('NATIVE_PATH_CONTROL_END',**rec,
             stdout_sha256=audit.sha(out/(name+'.stdout.txt')),stderr_sha256=audit.sha(out/(name+'.stderr.txt')))
        print(name,r.returncode,r.stdout,r.stderr)
    assert inputs=={str(p):audit.sha(p) for p in (fixture/'generated').rglob('*.java')}
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()

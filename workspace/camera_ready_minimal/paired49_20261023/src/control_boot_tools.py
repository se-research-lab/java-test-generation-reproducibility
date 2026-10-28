"""E-only Java 8 tools.jar loader control on unchanged fixture test bytes."""
import json,os,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

def main():
    stage=BASE/'evo_patch';fixture=stage/'fixtures/assertions_runtime_01'
    out=stage/'fixtures/boot_tools_07';out.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172');runtime=audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
    cp=os.pathsep.join(map(str,[fixture/'testclasses',fixture/'classes',runtime,
        Path('C:/Users/admin/.m2/repository/junit/junit/4.13.2/junit-4.13.2.jar'),
        Path('C:/Users/admin/.m2/repository/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar')]))
    locked=[jdk/'bin/java.exe',jdk/'lib/tools.jar',runtime,*sorted((fixture/'generated').rglob('*.java'))]
    hashes={str(p):audit.sha(p) for p in locked}
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
    env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env['PATH']
    results=[]
    for name,agent in [('boot_tools_dynamic',False),('boot_tools_premain',True)]:
        argv=[str(jdk/'bin/java.exe'),'-Xbootclasspath/a:'+str(jdk/'lib/tools.jar')]
        if agent:argv+=['-javaagent:'+str(runtime)]
        argv+=['-cp',cp,'org.junit.runner.JUnitCore','fixture.BranchFixture_ESTest']
        audit.log('BOOT_TOOLS_CONTROL_START',name=name,argv=argv,scope='E synthetic JVM only; no persistent environment change',input_hashes=hashes)
        r=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=60)
        for label,value in [('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+label+'.txt')).write_text(value,encoding='utf-8')
        rec={'name':name,'returncode':r.returncode,'pass':r.returncode==0 and 'OK (5 tests)' in r.stdout,'argv':argv,
             'stdout_sha256':audit.sha(out/(name+'.stdout.txt')),'stderr_sha256':audit.sha(out/(name+'.stderr.txt'))}
        results.append(rec);audit.log('BOOT_TOOLS_CONTROL_END',**rec);print(name,r.returncode,r.stdout,r.stderr)
    assert hashes=={str(p):audit.sha(p) for p in locked}
    (out/'results.json').write_text(json.dumps({'results':results,'input_hashes':hashes,'bytes_unchanged':True},indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()

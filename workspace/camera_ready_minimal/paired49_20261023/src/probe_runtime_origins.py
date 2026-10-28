"""Diagnose class origins and AttachProvider causes; never edit generated tests."""
import json, os, subprocess, sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

def main():
    stage=BASE/'evo_patch';fixture=stage/'fixtures/assertions_runtime_01'
    out=stage/'fixtures/runtime_origins_05';out.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172')
    runtime=audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
    jars=[runtime,Path('C:/Users/admin/.m2/repository/junit/junit/4.13.2/junit-4.13.2.jar'),
          Path('C:/Users/admin/.m2/repository/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'),jdk/'lib/tools.jar']
    cp=os.pathsep.join(map(str,[out,fixture/'testclasses',fixture/'classes',*jars]))
    source=out/'RuntimeOrigins.java'
    source.write_text('''import java.util.*;
public class RuntimeOrigins {
  public static void main(String[] args) throws Exception {
    for (String key : new String[]{"java.home","java.version","java.ext.dirs","java.library.path"})
      System.out.println(key+"="+System.getProperty(key));
    for (String name : new String[]{"org.evosuite.runtime.agent.AgentLoader","org.evosuite.runtime.EvoRunner",
      "com.sun.tools.attach.VirtualMachine","sun.tools.attach.WindowsAttachProvider"}) {
      try {Class<?> c=Class.forName(name);System.out.println(name+" loader="+c.getClassLoader()+" source="+c.getProtectionDomain().getCodeSource());}
      catch(Throwable t){t.printStackTrace();}
    }
    try {Class.forName("sun.tools.attach.WindowsAttachProvider").newInstance();System.out.println("CONSTRUCT_PROVIDER_OK");}
    catch(Throwable t){t.printStackTrace();}
    try {for(com.sun.tools.attach.spi.AttachProvider p:ServiceLoader.load(com.sun.tools.attach.spi.AttachProvider.class))System.out.println("SERVICE_PROVIDER="+p);}
    catch(Throwable t){t.printStackTrace();}
    System.out.println("PROVIDERS="+com.sun.tools.attach.spi.AttachProvider.providers());
    System.out.println("SECURITY_MANAGER="+System.getSecurityManager());
    org.junit.runner.Result r=org.junit.runner.JUnitCore.runClasses(Class.forName("fixture.BranchFixture_ESTest"));
    System.out.println("JUNIT runs="+r.getRunCount()+" failures="+r.getFailureCount());
    for(org.junit.runner.notification.Failure f:r.getFailures())f.getException().printStackTrace();
    System.exit(r.wasSuccessful()?0:1);
  }
}
''',encoding='utf-8')
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
    env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env.get('PATH','')
    records=[]
    for name,cmd in [('compile',[str(jdk/'bin/javac.exe'),'-cp',cp,str(source)]),
                     ('probe',[str(jdk/'bin/java.exe'),'-javaagent:'+str(runtime),'-cp',cp,'RuntimeOrigins'])]:
        audit.log('RUNTIME_ORIGIN_PROBE_START',name=name,argv=cmd)
        r=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=60)
        for label,value in [('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+label+'.txt')).write_text(value,encoding='utf-8')
        record={'name':name,'argv':cmd,'returncode':r.returncode,'stdout_sha256':audit.sha(out/(name+'.stdout.txt')),'stderr_sha256':audit.sha(out/(name+'.stderr.txt'))}
        records.append(record);audit.log('RUNTIME_ORIGIN_PROBE_END',**record)
        print(name,r.returncode,r.stdout,r.stderr)
        if name=='compile':assert r.returncode==0
    (out/'result.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()

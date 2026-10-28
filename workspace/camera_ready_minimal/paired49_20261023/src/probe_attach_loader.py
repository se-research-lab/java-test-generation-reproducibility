"""Expose the cause hidden by AttachProvider.providers(), in a new synthetic JVM."""
import json,os,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

def main():
    out=BASE/'evo_patch/fixtures/attach_loader_06';out.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172');runtime=audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
    source=out/'LoaderProbe.java'
    source.write_text('''import java.util.*;
public class LoaderProbe {
 public static void main(String[] args) throws Exception {
  ClassLoader loader=new org.evosuite.runtime.agent.ToolsJarLocator(null).getLoaderForToolsJar();
  System.out.println("LOADER="+loader);
  try {Object p=loader.loadClass("sun.tools.attach.WindowsAttachProvider").newInstance();System.out.println("PROVIDER="+p);}
  catch(Throwable t){t.printStackTrace();}
  Class type=loader.loadClass("com.sun.tools.attach.spi.AttachProvider");
  try {for(Object p:ServiceLoader.load(type,loader))System.out.println("SERVICE="+p);}
  catch(Throwable t){t.printStackTrace();}
  try {org.evosuite.runtime.agent.InstrumentingAgent.initialize();System.out.println("AGENT_OK");}
  catch(Throwable t){t.printStackTrace();System.exit(1);}
 }
}
''',encoding='utf-8')
    cp=os.pathsep.join(map(str,[out,runtime]))
    env=dict(os.environ);env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env['PATH']
    records=[]
    cmds=[('compile',[str(jdk/'bin/javac.exe'),'-cp',cp,str(source)]),
          ('loader',[str(jdk/'bin/java.exe'),'-cp',cp,'LoaderProbe']),
          ('nativepath',[str(jdk/'bin/java.exe'),'-Djava.library.path='+str(jdk/'jre/bin'),'-cp',cp,'LoaderProbe'])]
    for name,argv in cmds:
        audit.log('ATTACH_LOADER_START',name=name,argv=argv)
        r=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=45)
        for label,value in [('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+label+'.txt')).write_text(value,encoding='utf-8')
        rec={'name':name,'argv':argv,'returncode':r.returncode,'stdout_sha256':audit.sha(out/(name+'.stdout.txt')),'stderr_sha256':audit.sha(out/(name+'.stderr.txt'))}
        records.append(rec);audit.log('ATTACH_LOADER_END',**rec);print(name,r.returncode,r.stdout,r.stderr)
        if name=='compile':assert r.returncode==0
    (out/'results.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()

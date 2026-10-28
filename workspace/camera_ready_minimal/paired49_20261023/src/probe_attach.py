"""Diagnose the actual JDK8 attach provider error, without changing installed JDKs."""
import json,os,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit


def main():
    work=BASE/'evo_patch/fixtures/attach_probe_03';work.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172')
    src=work/'AttachProbe.java'
    src.write_text('''public class AttachProbe {
 public static void main(String[] args) {
  System.out.println("java.home="+System.getProperty("java.home"));
  System.out.println("java.library.path="+System.getProperty("java.library.path"));
  try { System.loadLibrary("attach"); System.out.println("attach library loaded"); } catch(Throwable t) {t.printStackTrace();}
  try { Class.forName("sun.tools.attach.WindowsAttachProvider").newInstance(); System.out.println("provider constructed"); } catch(Throwable t) {t.printStackTrace();}
  try { System.out.println(com.sun.tools.attach.spi.AttachProvider.providers()); } catch(Throwable t) {t.printStackTrace();}
 }
}''',encoding='utf-8')
    env=dict(os.environ);env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env['PATH']
    commands=[('compile',[str(jdk/'bin/javac.exe'),'-cp',str(jdk/'lib/tools.jar'),str(src)]),
              ('probe',[str(jdk/'bin/java.exe'),'-cp',str(work)+os.pathsep+str(jdk/'lib/tools.jar'),'AttachProbe'])]
    for name,argv in commands:
        audit.log('ATTACH_PROBE_START',argv=argv,name=name)
        result=subprocess.run(argv,cwd=work,env=env,capture_output=True,text=True,errors='replace',timeout=30)
        for label,text in [('stdout',result.stdout),('stderr',result.stderr)]:
            (work/(name+'.'+label+'.txt')).write_text(text,encoding='utf-8')
        audit.log('ATTACH_PROBE_END',name=name,returncode=result.returncode,
                  stdout_sha256=audit.sha(work/(name+'.stdout.txt')),stderr_sha256=audit.sha(work/(name+'.stderr.txt')))
        print(result.stdout);print(result.stderr)
        assert result.returncode==0


if __name__=='__main__':main()

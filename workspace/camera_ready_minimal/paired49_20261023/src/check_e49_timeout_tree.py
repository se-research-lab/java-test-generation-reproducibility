"""Actual Java parent/child timeout control, outside all study inputs."""
import importlib.util,json,subprocess,sys,time
from pathlib import Path
import psutil
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
spec=importlib.util.spec_from_file_location('driver',BASE/'src/e49_driver.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
out=BASE/'e49_driver/timeout_tree_control_01';out.mkdir(exist_ok=False)
src=out/'Sleeper.java'
src.write_text('''public class Sleeper { public static void main(String[] args) throws Exception {
 if(args.length==0) new ProcessBuilder(System.getProperty("java.home")+"/bin/java.exe","-cp",argsPath(),"Sleeper","child").start();
 Thread.sleep(60000); }
 static String argsPath(){return System.getProperty("java.class.path");}
}''',encoding='utf-8')
env=d.isolated_env(out)
compile_argv=[str(d.JDK/'bin/javac.exe'),str(src)]
r=subprocess.run(compile_argv,cwd=out,env=env,capture_output=True,text=True,timeout=30)
(out/'compile.stdout.txt').write_text(r.stdout,encoding='utf-8');(out/'compile.stderr.txt').write_text(r.stderr,encoding='utf-8')
assert r.returncode==0
controller=d.Commands(out,env,BASE,20261023)
start=time.monotonic()
try:controller.run([str(d.JDK/'bin/java.exe'),'-cp',str(out),'Sleeper'],cwd=out,timeout=2)
except subprocess.TimeoutExpired as exc:assert exc.timeout==2
else:raise AssertionError('Expected timeout did not occur')
event=next(e for e in reversed(audit.events()) if e['kind']=='EONLY_TIMEOUT_TREE_TERMINATED' and e['job']==str(out.relative_to(BASE)))
assert event['descendant_pids'],'Test did not exercise a child JVM'
for pid in event['descendant_pids']:
    if psutil.pid_exists(pid):
        try:psutil.Process(pid).wait(timeout=10)
        except psutil.NoSuchProcess:pass
        assert not psutil.pid_exists(pid),'Timed-out child still running'
assert controller.records[0]['returncode']==-999
report={'status':'PASS','timeout_seconds':2,'actual_elapsed_seconds':time.monotonic()-start,
 'descendant_JVMs_terminated':len(event['descendant_pids']),'no_surviving_child':True,
 'driver_sha256':audit.sha(BASE/'src/e49_driver.py'),'benchmark_classes':0,'GPT_API_calls':0}
d.write_json(out/'result.json',report);print(json.dumps(report,indent=2))

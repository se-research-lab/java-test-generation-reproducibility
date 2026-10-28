"""Synthetic-only Maven bridge to the tested process supervisor; no benchmark entry."""
import json,os,subprocess,shutil
from datetime import datetime,timezone
from pathlib import Path
import maven_adapter_v1 as a
from process_supervisor_v1 import Supervisor,environment

class SyntheticSupervisor(Supervisor):
 def verify(self,argv,cwd,timeout,tool_sha256,input_hashes):
  self.check_stop();argv=list(map(str,argv));cwd=Path(cwd).resolve();exe=Path(argv[0]).resolve()
  if self.out.name!='maven_runtime_fixture_v1' or not self.out.is_relative_to(a.R/'validation') or not cwd.is_relative_to(self.out):raise a.GuardAbort('Synthetic fixture boundary')
  if not 0<timeout<=300:raise a.GuardAbort('Timeout outside fixture policy')
  lock=json.loads((self.out/'fixture_lock.json').read_text(encoding='utf-8'))
  for path,h in lock['code_and_input_hashes'].items():
   if a.sha(path)!=h:raise a.GuardAbort('Fixture code/input drift')
  for path,h in input_hashes.items():
   if a.sha(path)!=h:raise a.GuardAbort('Command input drift')
  for path,h in lock['tools'].items():
   if a.sha(path)!=h:raise a.GuardAbort('Pinned tool/JAR drift')
  if exe not in {a.MVN.resolve(),(a.JDK/'bin/java.exe').resolve()} or lock['tools'].get(str(exe))!=tool_sha256 or a.sha(exe)!=tool_sha256:raise a.GuardAbort('Wrong tool')
  if exe==a.MVN.resolve():
   if '-o' not in argv or '-Dmaven.repo.local='+lock['cache'] not in argv:raise a.GuardAbort('Not private offline cache')
   if any(any(c in x for c in '\r\n&|<>^%!') for x in argv):raise a.GuardAbort('Maven shell metacharacter')
  elif argv[1:]!=['-version']:
   if '-class' not in argv or argv[argv.index('-class')+1]!='fixture.BranchFixture' or argv[-2:]!=['-seed','20261023']:raise a.GuardAbort('Non-synthetic Java command')
  return argv,cwd

class FixtureCommands:
 TimeoutExpired=subprocess.TimeoutExpired
 def __init__(self,out,cache,event):
  self.out=Path(out);self.cache=Path(cache);self.generations=0
  env=environment()
  for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','MAVEN_OPTS','MAVEN_ARGS']:
   if env.get(key):raise a.GuardAbort('Unqualified inherited runtime options: '+key)
  env['JAVA_HOME']=str(a.JDK);env['PATH']=str(a.JDK/'bin')+os.pathsep+env.get('PATH','')
  env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+str(a.JDK/'lib/tools.jar')+'"';(self.out/'temp').mkdir();env['TMP']=env['TEMP']=str(self.out/'temp')
  self.supervisor=SyntheticSupervisor(self.out,env,mode='fixture',event=event)
 def run(self,argv,**kw):
  argv=list(map(str,argv));name=Path(argv[0]).name.lower()
  if name in {'mvn','mvn.cmd'}:argv[0]=str(a.MVN);argv[1:1]=['-o','-Dmaven.repo.local='+str(self.cache)]
  elif name in {'java','java.exe'}:
   argv[0]=str(a.JDK/'bin/java.exe')
   if '-jar' in argv:
    argv=a.checked_generation_argv(argv,{'sample_index_1based':0,'seed':20261023,'build_tool':'maven','focal_path':'src/main/java/fixture/BranchFixture.java','reused_result':{}},self.out)
    self.generations+=1
    if self.generations>2:raise a.GuardAbort('Conditional retry maximum exceeded')
    status_path=a.R/'status.json';old=status_path.read_bytes();backup=self.out/f'status_before_generation_{self.generations:02d}.json'
    with backup.open('xb') as f:f.write(old)
    status=json.loads(old);status.update(updated_utc=datetime.now(timezone.utc).isoformat(),phase='SYNTHETIC MAVEN FIXTURE / NO BENCHMARK',fixture_EvoSuite_calls=self.generations,new_EvoSuite_calls=self.generations)
    temp=self.out/f'status_generation_{self.generations:02d}.tmp';a.dump(temp,status);temp.replace(status_path)
  else:raise a.GuardAbort('Fixture executable rejected')
  try:return self.supervisor.run(argv,kw.get('cwd',self.out),kw.get('timeout',300),a.sha(argv[0]),{})
  finally:
   if '-jar' in argv:
    dest=self.out/'generation_attempts'/f'{self.generations:02d}';dest.mkdir(parents=True,exist_ok=False);rows=[]
    for folder in [self.out/'repo/src/test/java',self.out/'repo/evosuite-report']:
     if not folder.exists():continue
     for p in sorted(folder.rglob('*')):
      if not p.is_file():continue
      rel=p.relative_to(self.out/'repo');target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True)
      with p.open('rb') as f,target.open('xb') as out:shutil.copyfileobj(f,out)
      if a.sha(target)!=a.sha(p):raise a.GuardAbort('Generation attempt archive mismatch')
      rows.append({'relative':rel.as_posix(),'sha256':a.sha(target)})
    a.dump(dest/'manifest.json',rows)
 def check_call(self,argv,**kw):
  r=self.run(argv,**kw)
  if r.returncode:raise subprocess.CalledProcessError(r.returncode,r.args)
  return 0

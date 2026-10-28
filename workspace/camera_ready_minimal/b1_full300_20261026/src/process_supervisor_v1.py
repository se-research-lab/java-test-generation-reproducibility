"""Serial, evidence-preserving subprocess supervisor. No automatic scheduler/resume.
Benchmark mode requires a separate admission document; no such admission is created here.
"""
import hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import GuardAbort,new_job_output,sha,dump,JDK,MVN,R

def now():return datetime.now(timezone.utc).isoformat()

class Supervisor:
 def __init__(self,out,env,mode='benchmark',admission=None,event=None):
  self.out=new_job_output(out);self.env=dict(env);self.mode=mode;self.event=event or (lambda *args,**kwargs:None)
  self.admission=admission;self.records=[];self.stop_files=[R/'STOP_REQUESTED.json',self.out/'STOP_REQUESTED.json']
  if not self.out.is_dir():raise GuardAbort('Job output must already exist')
  self.command_root=self.out/'commands';self.command_root.mkdir(exist_ok=False)
  if mode=='fixture':
   if not self.out.is_relative_to(R/'validation'):raise GuardAbort('Fixture mode only inside validation')
  elif mode!='benchmark':raise GuardAbort('Unknown supervisor mode')

 def check_stop(self):
  if any(p.exists() for p in self.stop_files):raise GuardAbort('B1 stop request; preserve evidence, explicit recovery required')

 def verify(self,argv,cwd,timeout,tool_sha256,input_hashes):
  self.check_stop();argv=list(map(str,argv));cwd=Path(cwd).resolve()
  if not cwd.is_relative_to(self.out) or not cwd.is_dir():raise GuardAbort('Command cwd outside owned job')
  if not 0<timeout<=300:raise GuardAbort('Timeout outside locked maximum')
  if not argv or not Path(argv[0]).is_absolute():raise GuardAbort('Executable must be absolute')
  exe=Path(argv[0]).resolve()
  if sha(exe)!=tool_sha256:raise GuardAbort('Executable hash drift')
  if any(k in self.env for k in ['OPENAI_API_KEY','ANTHROPIC_API_KEY']):raise GuardAbort('API credential in process environment')
  if any(any(token in k.upper() for token in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC','SECRET','PASSWORD','CREDENTIAL']) for k in self.env):raise GuardAbort('Unexpected credential-like environment variable')
  for p,h in input_hashes.items():
   if sha(p)!=h:raise GuardAbort('Command input hash drift')
  if self.mode=='fixture':
   if exe!=Path(sys.executable).resolve():raise GuardAbort('Only current Python allowed for supervisor fixture')
   if len(argv)!=5 or argv[1:4]!=['-B','-X','utf8']:raise GuardAbort('Fixture argv shape not allowed')
   source=Path(argv[4]).resolve()
   if not source.is_relative_to(self.out) or input_hashes.get(str(source))!=sha(source):raise GuardAbort('Fixture script must be owned and pinned')
  else:
   if self.admission is None:raise GuardAbort('No benchmark admission')
   p=Path(self.admission).resolve()
   if not p.is_relative_to(R):raise GuardAbort('External admission')
   admitted=json.loads(p.read_text(encoding='utf-8'))
   if not admitted.get('benchmark_admitted') or admitted.get('supervisor_sha256')!=sha(__file__):raise GuardAbort('Supervisor not admitted')
   if exe not in {(JDK/'bin/java.exe').resolve(),MVN.resolve()}:raise GuardAbort('Benchmark executable outside allowlist')
   if admitted.get('tool_hashes',{}).get(str(exe))!=tool_sha256:raise GuardAbort('Tool not admitted')
   # Only exact command plans signed by the admitted controller may execute.
   key=hashlib.sha256(json.dumps({'argv':argv,'cwd':str(cwd),'timeout':timeout},sort_keys=True).encode()).hexdigest()
   if key not in admitted.get('allowed_command_hashes',[]):raise GuardAbort('Command has no admission plan')
  if exe.suffix.lower() in {'.cmd','.bat'} and any(any(c in a for c in '\r\n&|<>^%!') for a in argv):raise GuardAbort('Shell metacharacter rejected')
  return argv,cwd

 def kill_owned(self,proc,created):
  """Kill only observed descendants of the exact live PID/start-time we spawned."""
  killed=[];errors=[]
  try:
   parent=psutil.Process(proc.pid)
   if parent.create_time()!=created:raise GuardAbort('PID reused: refusing termination')
   descendants=parent.children(recursive=True)
   identities=[(p.pid,p.create_time()) for p in descendants]
   # Stop parent first so it cannot create more descendants during teardown.
   try:parent.suspend()
   except psutil.NoSuchProcess:pass
   for pid,start in reversed(identities):
    try:
     child=psutil.Process(pid)
     if child.create_time()==start:child.kill();killed.append(pid)
    except psutil.NoSuchProcess:pass
    except psutil.Error as ex:errors.append({'pid':pid,'error':type(ex).__name__})
   try:parent.kill();killed.append(proc.pid)
   except psutil.NoSuchProcess:pass
  except psutil.NoSuchProcess:pass
  proc.wait(timeout=15)
  return {'owned_pid':proc.pid,'owned_create_time':created,'terminated_pids':killed,'errors':errors}

 def run(self,argv,cwd,timeout,tool_sha256,input_hashes):
  argv,cwd=self.verify(argv,cwd,timeout,tool_sha256,input_hashes)
  number=len(list(self.command_root.glob('[0-9][0-9][0-9]')))+1
  folder=self.command_root/f'{number:03d}';folder.mkdir(exist_ok=False)
  plan={'argv':argv,'cwd':str(cwd),'timeout_seconds':timeout,'executable_sha256':tool_sha256,'input_hashes':input_hashes,'mode':self.mode,'planned_utc':now()};dump(folder/'plan.json',plan)
  stdout=folder/'stdout.txt';stderr=folder/'stderr.txt';start=time.monotonic();reason=None;termination=None;rc=None;proc=None;created=None
  self.event('COMMAND_PLAN',path=str(folder),plan_sha256=sha(folder/'plan.json'))
  try:
   self.check_stop()
   with stdout.open('xb') as so,stderr.open('xb') as se:
    proc=subprocess.Popen(argv,cwd=cwd,env=self.env,stdout=so,stderr=se,stdin=subprocess.DEVNULL,shell=False,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    created=psutil.Process(proc.pid).create_time()
    dump(folder/'started.json',{'pid':proc.pid,'create_time':created,'started_utc':now()})
    self.event('COMMAND_STARTED',pid=proc.pid,create_time=created,folder=str(folder))
    while proc.poll() is None:
     if any(p.exists() for p in self.stop_files):reason='STOP_REQUESTED';break
     if time.monotonic()-start>=timeout:reason='TIMEOUT';break
     time.sleep(.1)
    if reason:termination=self.kill_owned(proc,created)
    rc=proc.wait(timeout=15)
  except BaseException as ex:
   if proc is not None and proc.poll() is None:termination=self.kill_owned(proc,created)
   reason=reason or type(ex).__name__
   dump(folder/'interrupted.json',{'at_utc':now(),'reason':reason,'detail':str(ex),'termination':termination,'auto_resume':False})
   raise
  finally:
   record={'index':number,'finished_utc':now(),'returncode':rc,'reason':reason,'elapsed_seconds':time.monotonic()-start,'termination':termination,'stdout_sha256':sha(stdout) if stdout.exists() else None,'stderr_sha256':sha(stderr) if stderr.exists() else None,'auto_resume':False}
   dump(folder/'finished.json',record);self.records.append(record);self.event('COMMAND_FINISHED',**record)
  out=stdout.read_text(encoding='utf-8',errors='replace');err=stderr.read_text(encoding='utf-8',errors='replace')
  if reason=='STOP_REQUESTED':raise GuardAbort('Stopped owned process; logs preserved; do not auto-retry')
  if reason=='TIMEOUT':raise subprocess.TimeoutExpired(argv,timeout,out,err)
  return subprocess.CompletedProcess(argv,rc,out,err)

def environment():
 blocked=['API_KEY','API_TOKEN','OPENAI','ANTHROPIC','SECRET','PASSWORD','CREDENTIAL']
 env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in blocked)}
 return env

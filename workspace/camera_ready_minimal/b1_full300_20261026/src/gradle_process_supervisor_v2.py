"""Gradle envelope prototype. NOT_RUNTIME_QUALIFIED; never creates admission.

Inherits the exact stream logging, stop checks and PID/start-time owned-tree
termination implementation already qualified with Python-only Maven fixtures.
No Gradle/Java execution is admitted by this source file or its validation.
"""
import json,os
from pathlib import Path
from maven_adapter_v1 import R,JDK,GuardAbort,sha
from process_supervisor_v1 import Supervisor as OwnedSupervisor,environment as stripped_environment
from gradle_command_policy_v2 import GradleCommandPolicy,PRIVATE_HOME,command_hash,ensure

def environment():
 env=stripped_environment()
 for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','JAVA_OPTS','GRADLE_OPTS','GRADLE_HOME','GRADLE_RO_DEP_CACHE']:
  ensure(not env.get(key),'Inherited unqualified runtime/cache option: '+key)
 env['JAVA_HOME']=str(JDK);env['GRADLE_USER_HOME']=str(PRIVATE_HOME.resolve())
 env['PATH']=str(JDK/'bin')+os.pathsep+env.get('PATH','')
 return env

class GradleSupervisor(OwnedSupervisor):
 def __init__(self,out,env,job,context,admission=None,event=None):
  super().__init__(out,env,mode='benchmark',admission=admission,event=event)
  self.mode='gradle_guard_v2';self.job=job;self.context=context;self.stage=None
  self.batch_admission=Path(admission).resolve() if admission is not None else None

 def verify(self,argv,cwd,timeout,tool_sha256,input_hashes):
  self.check_stop()
  ensure(self.batch_admission is not None,'No explicit Gradle execution admission')
  path=self.batch_admission;ensure(path.is_relative_to(R.resolve()) and path.is_file(),'Admission outside B1 or missing')
  lock=json.loads(path.read_text(encoding='utf-8'))
  ensure(lock.get('schema')=='B1_gradle_supervisor_v2','Unknown Gradle admission schema')
  ensure(lock.get('Gradle_execution_admitted') is True and lock.get('GPT_generation_authorized') is False,'Gradle execution is not explicitly admitted as E-only')
  scope=lock.get('execution_scope');ensure(scope in {'runtime_qualification','benchmark'},'Unknown execution scope')
  if scope=='benchmark':ensure(lock.get('Gradle_runtime_qualified') is True,'Gradle benchmark requires runtime qualification')
  ensure(lock.get('supervisor_sha256')==sha(__file__),'Gradle supervisor not pinned')
  ensure(lock.get('base_supervisor_sha256')==sha(R/'src/process_supervisor_v1.py'),'Owned-process supervisor drift')
  ensure(lock.get('command_policy_sha256')==sha(R/'src/gradle_command_policy_v2.py'),'Gradle policy drift')
  ensure(not any(any(t in key.upper() for t in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC','SECRET','PASSWORD','CREDENTIAL']) for key in self.env),'Credential-like process environment')
  ensure(self.env.get('JAVA_HOME')==str(JDK) and Path(self.env.get('GRADLE_USER_HOME','')).resolve()==PRIVATE_HOME.resolve(),'Runtime Java/private Gradle home drift')
  for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','JAVA_OPTS','GRADLE_OPTS','GRADLE_HOME','GRADLE_RO_DEP_CACHE']:
   ensure(not self.env.get(key),'Unqualified runtime option: '+key)
  for records in [lock.get('code_and_input_hashes',{}),input_hashes]:
   for p,h in records.items():ensure(sha(p)==h,'Code/input hash drift: '+str(p))
  policy=GradleCommandPolicy(self.out,self.job,self.context,lock)
  args,cwd=policy.validate(argv,cwd,timeout,self.stage);exe=Path(args[0]).resolve()
  ensure(lock.get('tool_hashes',{}).get(str(exe))==tool_sha256 and sha(exe)==tool_sha256,'Executable hash differs')
  ensure(command_hash(args,cwd,timeout) in lock.get('allowed_command_hashes',[]),'Exact command has no admission hash')
  return args,cwd

 def run(self,argv,cwd,timeout,tool_sha256,input_hashes,stage):
  ensure(self.stage is None,'No concurrent/reentrant Gradle command')
  self.stage=stage
  try:return super().run(argv,cwd,timeout,tool_sha256,input_hashes)
  finally:self.stage=None

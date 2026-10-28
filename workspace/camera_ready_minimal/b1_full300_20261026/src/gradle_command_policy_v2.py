"""Pure Gradle40 command guard prototype. NOT_RUNTIME_QUALIFIED; no admission.

Only validates an explicitly pinned plan. It never launches a tool, rewrites a
build, chooses a framework/provider, or changes the historical metric/parser.
"""
import hashlib,json,re
from pathlib import Path
from maven_adapter_v1 import R,JDK,GuardAbort,sha,new_job_output

PRIVATE_HOME=R/'cache_preparation_gradle_v1/gradle_user_home'
CONTEXT=R/'inputs/gradle40_context_v2/manifest.json'
SLOTS={
 '2.13':('gradle-2.13-all','1b9wlm73elu4cqnbc0rk7r7qn'),
 '5.2.1':('gradle-5.2.1-bin','9lc4nzslqh3ep7ml2tp68fk8s'),
 '6.9.4':('gradle-6.9.4-bin','5a0lguq60r1skx3y8d5qdl7d9'),
 '8.14.4':('gradle-8.14.4-bin','92wwslzcyst3phie3o264zltu'),
}
TASKS={'classes','b1WriteClasspaths','b1NativeTest','b1NativeJacocoReport','pitest','clean'}
STAGES={
 'compile_classpath':{'classes','b1WriteClasspaths','clean'},
 'classpath':{'b1WriteClasspaths'},
 'test_jacoco':{'b1NativeTest','b1NativeJacocoReport','clean'},
 'pit':{'pitest'},
}

def ensure(ok,message):
 if not ok:raise GuardAbort(message)

def launcher_paths():
 return {version:(PRIVATE_HOME/'wrapper/dists'/slot/hashdir/('gradle-'+version)/'bin/gradle.bat').resolve() for version,(slot,hashdir) in SLOTS.items()}

def command_hash(argv,cwd,timeout):
 return hashlib.sha256(json.dumps({'argv':list(map(str,argv)),'cwd':str(Path(cwd).resolve()),'timeout':timeout},sort_keys=True).encode()).hexdigest()

def tool_paths(lock):
 """An admitted dictionary alone cannot extend this fixed executable set."""
 ensure(Path(lock['gradle_user_home']).is_absolute(),'Gradle user home must be absolute')
 home=Path(lock['gradle_user_home']).resolve()
 ensure(home==PRIVATE_HOME.resolve(),'Shared or unexpected Gradle user home')
 ensure(all(Path(v).is_absolute() for v in lock['gradle_launchers'].values()),'Gradle launchers must be absolute')
 expected=launcher_paths();provided={k:Path(v).resolve() for k,v in lock['gradle_launchers'].items()}
 ensure(provided==expected,'Gradle launcher/version/hash-slot mapping differs')
 java=(JDK/'bin/java.exe').resolve();ensure(Path(lock['java_executable']).is_absolute() and Path(lock['java_executable']).resolve()==java,'Unqualified Java executable')
 allowed=set(expected.values())|{java}
 for p in allowed:
  h=lock.get('tool_hashes',{}).get(str(p))
  ensure(isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) is not None,'Missing exact executable hash: '+str(p))
 return allowed

class GradleCommandPolicy:
 """Metadata-bound grammar; validation is deliberately separate from admission."""
 def __init__(self,out,job,context,lock):
  self.out=new_job_output(out);self.lock=lock;self.job=job;self.context=context
  self.allowed=tool_paths(lock)
  ensure(job.get('build_tool')=='gradle' and not job.get('reused_result'),'Not a new Gradle40 job')
  index=job['sample_index_1based'];ensure(index in lock['admitted_sample_indices'],'Sample outside declared plan')
  ensure(Path(lock['gradle_context_path']).is_absolute(),'Metadata path must be absolute')
  metadata=Path(lock['gradle_context_path']).resolve()
  ensure(metadata==CONTEXT.resolve(),'Unexpected metadata file')
  ensure(sha(metadata)==lock['gradle_context_sha256'],'Gradle40 context hash drift')
  rows=json.loads(metadata.read_text(encoding='utf-8'));matches=[r for r in rows if r['sample_index_1based']==index]
  ensure(len(matches)==1 and matches[0]==context,'Context is not the pinned metadata row')
  for field in ['class_key','repo_id']:ensure(job[field]==context[field],'Context identity mismatch: '+field)
  ensure(job['seed']==context['original_seed'],'Original generation seed changed')
  ensure(context['Gradle_version'] in SLOTS,'Unqualified Gradle version')
  repo=self.out/'repo';self.build_root=(repo/context['build_root_relative_to_repo']).resolve();self.module=(repo/context['module_dir_relative_to_repo']).resolve()
  ensure(self.build_root.is_relative_to(repo.resolve()) and self.module.is_relative_to(self.build_root),'Build root/module outside owned repository')
  self.launcher=launcher_paths()[context['Gradle_version']]
  selector=context['module_selector'];prefix='' if selector=='.' else ':'+selector.replace('/',':').strip(':')+':'
  ensure(context['task_prefix']==prefix,'Metadata task-prefix mismatch')
  self.prefix=prefix

 def init_arguments(self):
  record=self.lock.get('init_script')
  if record is None:return []
  ensure(Path(record['path']).is_absolute(),'Init script path must be absolute')
  p=Path(record['path']).resolve()
  ensure(p.is_relative_to(self.out) and p.suffix in {'.gradle','.kts'} and p.is_file(),'Init script outside owned job or missing')
  ensure(sha(p)==record['sha256'],'Init script hash drift')
  ensure(self.lock.get('code_and_input_hashes',{}).get(str(p))==record['sha256'],'Init script is not pinned with code inputs')
  return ['--init-script',str(p)]

 def validate(self,argv,cwd,timeout,stage):
  args=list(map(str,argv));cwd=Path(cwd).resolve()
  ensure(args and Path(args[0]).is_absolute(),'Executable must be absolute')
  exe=Path(args[0]).resolve();ensure(exe in self.allowed,'Executable outside fixed Gradle/JDK8 allowlist')
  ensure(cwd==self.build_root and cwd.is_dir(),'Cwd must be exact owned metadata build root')
  ensure(isinstance(timeout,int) and not isinstance(timeout,bool) and 0<timeout<=900,'Timeout outside locked integer maximum900')
  plans=self.lock.get('gradle_task_plans',{});ensure(stage in plans,'Stage lacks an exact admitted task plan')
  plan=plans[stage];ensure(timeout==plan['timeout_seconds'],'Stage timeout differs from plan')
  tail=list(map(str,plan['argv_tail']))
  qualification=self.lock.get('execution_scope')=='runtime_qualification'
  if exe==(JDK/'bin/java.exe').resolve():
   ensure(qualification and stage=='java_version' and tail==['-version'] and timeout==15,'Prototype Java permits qualification -version only; EvoSuite guard not wired')
   expected=[str(exe),'-version']
  else:
   ensure(exe==self.launcher,'Launcher does not match this job metadata')
   head=[str(exe),'--offline','--no-daemon','-g',str(PRIVATE_HOME.resolve()),*self.init_arguments()]
   if stage in {'version','help'}:
    ensure(qualification,'Version/help are qualification-only')
    if stage=='version':ensure(self.lock.get('init_script') is None,'Version qualification forbids init scripts')
    ensure(tail==(['--version'] if stage=='version' else ['help']),'Qualification tail changed')
    ensure(timeout in {30,60},'Qualification timeout not30/60')
   else:
    ensure(stage in STAGES and timeout==900,'Legacy Gradle stages require an explicit900s plan')
    ensure(tail and len(tail)==len(set(tail)),'Empty or duplicate Gradle tasks')
    basenames=[]
    for task in tail:
     ensure(task.startswith(self.prefix),'Wrong module task prefix')
     name=task[len(self.prefix):]
     ensure(name in TASKS and name in STAGES[stage],'Task outside stage/module allowlist')
     ensure(task==self.prefix+name,'Nested or abbreviated task refused')
     basenames.append(name)
    ensure('clean' not in basenames or basenames[0]=='clean','Clean may precede stage tasks only')
    if stage=='compile_classpath':ensure('classes' in basenames,'Compile stage must include classes')
    if stage=='test_jacoco':ensure({'b1NativeTest','b1NativeJacocoReport'}<=set(basenames),'Measurement must name both dedicated native tasks')
   expected=head+tail
  ensure(args==expected,'Command differs from exact offline/private-home/init/task plan')
  if exe.suffix.lower() in {'.bat','.cmd'}:ensure(not any(any(c in a for c in '\r\n&|<>^%!') for a in args),'Shell metacharacter rejected')
  return args,cwd

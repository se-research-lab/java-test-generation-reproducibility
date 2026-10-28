"""Production command bridge. Requires externally sealed code/input admission.
No entry point, no scheduler, and never creates batch admission itself.
"""
import json,os,subprocess,shutil,hashlib
from pathlib import Path
from maven_adapter_v1 import R,JDK,MVN,GuardAbort,sha,dump,checked_generation_argv,generation_bindings
from process_supervisor_v1 import Supervisor,environment

class MavenCommands:
 TimeoutExpired=subprocess.TimeoutExpired
 def __init__(self,out,job,admission,event):
  self.out=Path(out).resolve();self.job=job;self.admission=Path(admission);self.event=event;self.records=[];self.generations=0
  self.lock=json.loads(self.admission.read_text(encoding='utf-8'));self.cache=Path(self.lock['cache']).resolve()
  self.verify_lock()
  if self.lock.get('scope')=='synthetic_controller_fixture':
   if self.out!=(R/'validation/maven_controller_fixture_v1').resolve() or job['class_key']!='synthetic:fixture.BranchFixture' or job['sample_index_1based']!=0 or job['selected_test_fqcn']!='fixture.BranchFixture_ESTest':raise GuardAbort('Synthetic scope mismatch')
  elif not self.out.is_relative_to((R/'jobs').resolve()):raise GuardAbort('Benchmark job must be inside B1/jobs')
  if job['sample_index_1based'] not in self.lock['admitted_sample_indices']:raise GuardAbort('Class outside admission')
  if job['build_tool']!='maven' or job['reused_result']:raise GuardAbort('Not a new Maven class')
  if self.cache!=(R/'cache_preparation_v1/maven_cache').resolve():raise GuardAbort('Wrong cache')
  env=environment()
  for k in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','MAVEN_OPTS','MAVEN_ARGS']:
   if env.get(k):raise GuardAbort('Inherited runtime options not qualified: '+k)
  env['JAVA_HOME']=str(JDK);env['PATH']=str(JDK/'bin')+os.pathsep+env.get('PATH','');env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+str(JDK/'lib/tools.jar')+'"'
  tmp=self.out/'temp';tmp.mkdir(exist_ok=False);env['TMP']=env['TEMP']=str(tmp)
  self.supervisor=Supervisor(self.out,env,mode='benchmark',event=event)
  # Function loading only obtains the unchanged fixed skip-arg list; no project code import.
  self.skip=generation_bindings(self,self.out,event)['common_maven_skip_args']()
  manifest=R.parent/'paired49_20261023/e1_compatibility_diagnostic_v1/cache_copy_manifest.json'
  if sha(manifest)!=self.lock['cache_manifest_sha256']:raise GuardAbort('Cache manifest not pinned')
  self.cache_hashes={x['relative']:x['sha256'] for x in json.loads(manifest.read_text(encoding='utf-8'))}
 def verify_lock(self):
  allowed=self.lock.get('benchmark_admitted') or (self.lock.get('scope')=='synthetic_controller_fixture' and self.lock.get('synthetic_execution_admitted') and self.lock.get('benchmark_admitted') is False)
  if not allowed or self.lock.get('GPT_generation_authorized') is not False:raise GuardAbort('Execution not admitted as E-only')
  for p,h in self.lock['code_and_input_hashes'].items():
   if sha(p)!=h:raise GuardAbort('Admission code/input drift: '+str(p))
  for p,h in self.lock['tool_hashes'].items():
   if sha(p)!=h:raise GuardAbort('Admission tool drift')
 def run(self,argv,**kw):
  self.verify_lock();self.supervisor.check_stop();args=list(map(str,argv));cwd=Path(kw.get('cwd',self.out)).resolve();timeout=kw.get('timeout',300)
  if not cwd.is_relative_to(self.out):raise GuardAbort('Command cwd outside job')
  exe=Path(args[0]).name.lower();generation=False
  if exe in {'mvn','mvn.cmd'}:
   args=self.maven_args(args,cwd,timeout)
  elif exe in {'java','java.exe'}:
   args[0]=str(JDK/'bin/java.exe')
   if args[1:]!=['-version']:
    args=checked_generation_argv(args,self.job,self.out);generation=True
    if timeout!=240:raise GuardAbort('Generation timeout changed')
    if self.generations>=2:raise GuardAbort('More than conditional two generation attempts')
    if self.generations:
     prior=self.records[-1]
     if prior.get('generation') is not True:raise GuardAbort('Unexpected retry ordering')
     ns=generation_bindings(self,self.out,self.event)
     if not ns['should_retry_evosuite_with_sanitized_classpath'](prior['stdout']+'\n'+prior['stderr']):raise GuardAbort('Retry lacks accepted technical trigger')
     oldcp=prior['argv'][prior['argv'].index('-projectCP')+1].split(os.pathsep)
     sanitized,_=ns['sanitize_evosuite_generation_classpath'](oldcp)
     if args[args.index('-projectCP')+1]!=os.pathsep.join(sanitized) or sanitized==oldcp:raise GuardAbort('Retry is not exact sanitized classpath')
    self.generations+=1
   elif timeout!=15:raise GuardAbort('Java version timeout changed')
  else:raise GuardAbort('Executable outside Maven/EvoSuite allowlist')
  if generation:self.verify_classpath(args[args.index('-projectCP')+1])
  index=len(self.records)+1;ticket=self.out/'command_admissions'/f'{index:03d}.json'
  key=hashlib.sha256(json.dumps({'argv':args,'cwd':str(cwd),'timeout':timeout},sort_keys=True).encode()).hexdigest()
  dump(ticket,{'benchmark_admitted':True,'supervisor_sha256':sha(R/'src/process_supervisor_v1.py'),'tool_hashes':self.lock['tool_hashes'],'allowed_command_hashes':[key],'batch_admission_sha256':sha(self.admission),'validator_sha256':sha(__file__)})
  self.supervisor.admission=ticket;result=None;error=None
  try:
   result=self.supervisor.run(args,cwd,timeout,self.lock['tool_hashes'][str(Path(args[0]).resolve())],{})
   return result
  except subprocess.TimeoutExpired as ex:error=ex;raise
  finally:
   record={'argv':args,'generation':generation,'returncode':result.returncode if result else None,'timeout':error is not None,'stdout':result.stdout if result else (error.stdout or '' if error else ''),'stderr':result.stderr if result else (error.stderr or '' if error else '')}
   self.records.append(record)
   if generation:self.archive_attempt()
 def check_call(self,argv,**kw):
  r=self.run(argv,**kw)
  if r.returncode:raise subprocess.CalledProcessError(r.returncode,r.args)
  return 0
 def verify_classpath(self,cp):
  rows=[]
  cachelock=json.loads((R/'cache_preparation_v1/protocol.json').read_text(encoding='utf-8'))
  manifest=R.parent/'paired49_20261023/e1_compatibility_diagnostic_v1/cache_copy_manifest.json'
  if sha(manifest)!=cachelock['manifest_sha256']:raise GuardAbort('Cache input manifest drift')
  expected={x['relative']:x['sha256'] for x in json.loads(manifest.read_text(encoding='utf-8'))}
  for value in cp.split(os.pathsep):
   p=Path(value).resolve()
   if p.is_dir():
    if not p.is_relative_to(self.out/'repo') or p.name!='classes' or p.parent.name!='target':raise GuardAbort('External production class directory')
    rows.append({'path':str(p),'type':'production_classes','classes':{q.relative_to(p).as_posix():sha(q) for q in p.rglob('*.class')}})
   elif p.is_file():
    h=sha(p)
    if p.is_relative_to(self.cache):
     if expected.get(p.relative_to(self.cache).as_posix())!=h:raise GuardAbort('Dependency JAR differs from accepted cache')
    elif self.lock['tool_hashes'].get(str(p))!=h:raise GuardAbort('External classpath JAR not pinned')
    rows.append({'path':str(p),'sha256':h})
   else:raise GuardAbort('Missing classpath element')
  dump(self.out/'classpath_guards'/f'{self.generations:02d}.json',rows)
 def maven_args(self,args,cwd,timeout):
  module=(self.out/'repo'/self.job['module']).resolve()
  if cwd!=module:raise GuardAbort('Unexpected module cwd')
  settings=['-s',str(self.out/'settings.xml')] if (self.out/'settings.xml').is_file() else []
  head=[*settings,*self.skip];generation=[*head,'-DskipTests=true','compile','dependency:build-classpath','-Dmdep.outputFile='+str(module/'target/evosuite-classpath.txt')]
  test=self.job['selected_test_fqcn'];measurement=[*settings,'-Dtest='+test,*self.skip,'clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:mutationCoverage']
  tail=args[1:]
  if tail in [generation,measurement]:
   if timeout!=300:raise GuardAbort('Maven lifecycle timeout changed')
  else:
   # Dependency/effective-POM audits have declared plugin goals and bounded output files.
   base=[*settings,'-Dtest='+test,*self.skip]
   if tail[:len(base)]!=base or timeout!=180:raise GuardAbort('Unknown Maven command prefix')
   rest=tail[len(base):];allowed_goals={'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:tree','org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath','org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom'}
   goals=[]
   for arg in rest:
    if arg in allowed_goals:goals.append(arg)
    elif arg in {'-DincludeScope=test','-DincludeScope=compile'}:pass
    elif any(arg.startswith(k) for k in ['-DoutputFile=','-Dmdep.outputFile=','-Doutput=']):
     dest=Path(arg.split('=',1)[1]).resolve()
     if dest.parent!=self.out or dest.exists():raise GuardAbort('Dependency audit output outside job or already exists')
    else:raise GuardAbort('Unknown Maven audit argument')
   if not goals or len(goals)!=len(set(goals)):raise GuardAbort('Invalid Maven audit goals')
  return [str(MVN),'-o','-Dmaven.repo.local='+str(self.cache),*tail]
 def archive_attempt(self):
  out=self.out/'generation_attempts'/f'{self.generations:02d}';out.mkdir(parents=True,exist_ok=False);rows=[]
  module=self.out/'repo'/self.job['module']
  for folder in [module/'src/test/java',module/'evosuite-report']:
   if not folder.is_dir():continue
   for p in sorted(folder.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(module);dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    with p.open('rb') as f,dest.open('xb') as t:shutil.copyfileobj(f,t)
    if sha(dest)!=sha(p):raise GuardAbort('Attempt archive mismatch')
    rows.append({'path':rel.as_posix(),'sha256':sha(dest)})
  dump(out/'manifest.json',rows)

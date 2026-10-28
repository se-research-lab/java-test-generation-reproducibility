"""No generation entry point. Exact Maven audit/compile/measurement commands only."""
import json,os,hashlib,subprocess
from pathlib import Path
from maven_adapter_v1 import R,JDK,MVN,sha,dump,GuardAbort,generation_bindings
from process_supervisor_v1 import Supervisor,environment
from b1_maven_commands_v3 import MavenCommands
from parallel_pin_verify_v1 import verify_pins
class MeasurementCommands(MavenCommands):
 def __init__(self,out,job,admission,event):
  self.out=Path(out).resolve();self.job=job;self.admission=Path(admission);self.event=event;self.records=[];self.generations=0
  self.lock=json.loads(self.admission.read_text());self.cache=R/'cache_preparation_v1/maven_cache'
  assert self.lock['generation_allowed'] is False and self.lock['GPT_generation_authorized'] is False
  assert self.lock['job']==job and self.lock['output']==str(self.out)
  self.pins=self.lock['code_and_input_hashes'];assert self.pins[str(Path(__file__).resolve())]==sha(__file__);verify_pins(self.pins)
  env=environment()
  for k in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','MAVEN_OPTS','MAVEN_ARGS']:assert not env.get(k)
  env['JAVA_HOME']=str(JDK);env['PATH']=str(JDK/'bin')+os.pathsep+env.get('PATH','');env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+str(JDK/'lib/tools.jar')+'"'
  (self.out/'temp').mkdir();env['TMP']=env['TEMP']=str(self.out/'temp')
  self.supervisor=Supervisor(self.out,env,mode='benchmark',event=event)
  self.skip=generation_bindings(None,self.out,event)['common_maven_skip_args']()
  cache_manifest=R.parent/'paired49_20261023/e1_compatibility_diagnostic_v1/cache_copy_manifest.json'
  self.cache_hashes={x['relative']:x['sha256'] for x in json.loads(cache_manifest.read_text())}
 def verify_lock(self):verify_pins(self.pins);verify_pins(self.lock['tool_hashes'])
 def run(self,argv,**kw):
  self.verify_lock();args=list(map(str,argv));cwd=Path(kw.get('cwd',self.out)).resolve();timeout=kw.get('timeout',300)
  if Path(args[0]).name.lower() in {'java','java.exe'}:
   assert args==[str(JDK/'bin/java.exe'),'-version'] and timeout==15,'Java generation forbidden; version probe only'
  else:
   assert Path(args[0]).name.lower() in {'mvn','mvn.cmd'},'Only Maven measurement permitted'
   args=self.maven_args(args,cwd,timeout)
  key=hashlib.sha256(json.dumps({'argv':args,'cwd':str(cwd),'timeout':timeout},sort_keys=True).encode()).hexdigest()
  p=self.out/'command_admissions'/f'{len(self.records)+1:03d}.json'
  dump(p,{'benchmark_admitted':True,'scope':self.lock['scope'],'supervisor_sha256':sha(R/'src/process_supervisor_v1.py'),'tool_hashes':self.lock['tool_hashes'],'allowed_command_hashes':[key],'generation_allowed':False,'parent_sha256':sha(self.admission)})
  self.supervisor.admission=p
  try:
   r=self.supervisor.run(args,cwd,timeout,self.lock['tool_hashes'][str(Path(args[0]).resolve())],{});self.records.append({'argv':args,'returncode':r.returncode,'timeout':False,'stdout':r.stdout,'stderr':r.stderr});return r
  except subprocess.TimeoutExpired as ex:
   self.records.append({'argv':args,'returncode':None,'timeout':True,'stdout':ex.stdout or '', 'stderr':ex.stderr or ''});raise

 def maven_args(self,args,cwd,timeout):
  module=(self.out/'repo'/self.job['module']).resolve()
  settings=['-s',str(self.out/'settings.xml')] if (self.out/'settings.xml').is_file() else []
  expected=[*settings,'-Dtest='+self.job['selected_test_fqcn'],*self.skip,'clean','test','jacoco:prepare-agent','jacoco:report']
  if args[1:]==expected:
   assert Path(cwd).resolve()==module and timeout==300,'Test-only stage boundary'
   return [str(MVN),'-o','-Dmaven.repo.local='+str(self.cache),*args[1:]]
  return super().maven_args(args,cwd,timeout)

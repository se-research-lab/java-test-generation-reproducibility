"""B1 Maven adapter building blocks. No process launcher or benchmark entry point.
Generation/policy function bodies are E49-identical; only namespace/output bindings differ.
"""
import ast,copy,difflib,hashlib,json,os,re,shutil,time,types,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
R=Path(__file__).resolve().parents[1]
WORKSPACE=R.parents[1]
JDK=Path('C:/Program Files/Java/jdk1.8.0_172')
MVN=Path('C:/Program Files/Apache/maven/bin/mvn.cmd')
NS={'m':'http://maven.apache.org/POM/4.0.0'}

class GuardAbort(BaseException):
 """Intentionally bypass legacy helpers' broad `except Exception` handlers."""

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def owned(path):
 p=Path(path).resolve()
 if not p.is_relative_to(R.resolve()) or p==R.resolve():raise GuardAbort('Not inside isolated B1 output')
 return p
def new_job_output(path):
 p=owned(path)
 if not any(p.is_relative_to((R/name).resolve()) for name in ['jobs','validation']):raise GuardAbort('Job must be inside jobs or validation')
 return p
def bindings(relative,namespace):
 report=json.loads((R/'audit/adapter_extraction_v1.json').read_text(encoding='utf-8'))
 record=next(x for x in report['modules'] if x['target']==relative);p=R/relative
 if sha(p)!=record['target_sha256']:raise GuardAbort('Extracted adapter drift')
 tree=ast.parse(p.read_text(encoding='utf-8'));functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
 if [n.name for n in functions]!=record['functions']:raise GuardAbort('Function whitelist changed')
 if any(isinstance(n,(ast.Import,ast.ImportFrom)) for f in functions for n in ast.walk(f)):raise GuardAbort('Unexpected import')
 exec(compile(ast.Module(body=functions,type_ignores=[]),str(p),'exec'),namespace)
 return namespace
def profile():
 ns=bindings('adapters/e49_profile.py',{'LEGACY':'submitted_legacy','REVIEWER':'reviewer_assertions'})
 return types.SimpleNamespace(**{k:ns[k] for k in ['LEGACY','REVIEWER','maven_generation_options']})
def reviewer_options():
 p=profile();flags=p.maven_generation_options(p.REVIEWER)
 expected=json.loads((R/'protocol.json').read_text(encoding='utf-8'))['generation_options']
 if len(flags)!=len(expected) or set(flags)!=set(expected):raise GuardAbort('Generation profile mismatch')
 return flags

def generation_bindings(commands,out,event):
 out=new_job_output(out);p=profile()
 def write_text(path,content):
  path=Path(path).resolve()
  if not path.is_relative_to(out):raise GuardAbort('Helper write outside job')
  path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
 def phase(*args,**kw):event('PHASE',phase=str(args[0]),**{k:str(v) for k,v in kw.items()})
 ns={'os':os,'time':time,'Path':Path,'zipfile':zipfile,'re':re,'ET':ET,'subprocess':commands,'evosuite_profile':p,
     'utils':types.SimpleNamespace(append_phase_log=phase,write_text_file=write_text),
     'toolchains':types.SimpleNamespace(evosuite_jar=lambda:str(WORKSPACE/'scripts_v2/evosuite-1.2.0.jar'),evosuite_runtime_jar=lambda:str(WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar')),
     'errorCorrection':types.SimpleNamespace(extract_errors=lambda a,b:(a+'\n'+b)[-2500:]),
     'MAVEN_TIMEOUT_SECONDS':300,'EVOSUITE_TIMEOUT_SECONDS':240,
     'EVOSUITE_TEST_FRAMEWORK_JAR_PATTERNS':['junit','jupiter','hamcrest','mockito','byte-buddy','objenesis','opentest4j','apiguardian'],
     'java_command':lambda system:str(JDK/'bin/java.exe'),'maven_command':lambda system:str(MVN),
     'maven_settings_args':lambda:['-s',str(out/'settings.xml')] if (out/'settings.xml').is_file() else [],'jdk_tools_jar':lambda:str(JDK/'lib/tools.jar')}
 return bindings('adapters/e49_generation_functions.py',ns)

def measurement_policy_bindings(event):
 return bindings('adapters/e49_measurement_policy.py',{'ET':ET,'NS':NS,'copy':copy,'re':re,'zipfile':zipfile,'Path':Path,'shutil':shutil,'difflib':difflib,'audit':types.SimpleNamespace(sha=sha),'dump':dump,'event':event})

def native_suite(module,test_fqcn):
 if not re.fullmatch(r'[\w$]+(?:\.[\w$]+)*_ESTest',test_fqcn):raise GuardAbort('Invalid native test name')
 path=Path(module)/'src/test/java'/Path(*test_fqcn.split('.'));parent=path.parent
 names={path.name+'.java',path.name+'_scaffolding.java'}
 # Name equality is case-sensitive even on Windows. Never use *ESTest*.java glob.
 found={p.name:p for p in parent.iterdir() if p.is_file() and p.name in names} if parent.is_dir() else {}
 return {'test':found.get(path.name+'.java'),'scaffolding':found.get(path.name+'_scaffolding.java'),'complete':set(found)==names,'files':[{'path':str(p),'sha256':sha(p)} for p in sorted(found.values())]}

def checked_generation_argv(argv,job,out):
 out=new_job_output(out);argv=list(map(str,argv))
 if job.get('reused_result') or job.get('status')=='REUSED_VERIFIED_E49':raise GuardAbort('Refuse regeneration of accepted E49')
 if job['build_tool']!='maven':raise GuardAbort('Maven adapter cannot admit Gradle')
 if job['seed']!=20261023+job['sample_index_1based']:raise GuardAbort('Seed rule changed')
 if not argv or Path(argv[0]).resolve()!=(JDK/'bin/java.exe').resolve():raise GuardAbort('Wrong JVM')
 def one(flag):
  if argv.count(flag)!=1 or argv.index(flag)+1>=len(argv):raise GuardAbort('Missing/duplicate argv key: '+flag)
  return argv[argv.index(flag)+1]
 if Path(one('-jar')).resolve()!=(WORKSPACE/'scripts_v2/evosuite-1.2.0.jar').resolve():raise GuardAbort('Wrong EvoSuite JAR')
 expected_class=job['focal_path'].split('/src/main/java/',1)[-1].removesuffix('.java').replace('/','.')
 if one('-class')!=expected_class:raise GuardAbort('Wrong focal FQCN')
 one('-projectCP')
 for flag in reviewer_options():
  key=flag.split('=',1)[0]+'='
  if [a for a in argv if a.startswith(key)]!=[flag]:raise GuardAbort('Profile override: '+key)
 allowed={f.split('=',1)[0] for f in reviewer_options()}|{'-Dtest_dir','-Dreport_dir'}
 if any(a.startswith('-D') and a.split('=',1)[0] not in allowed for a in argv):raise GuardAbort('Undeclared EvoSuite parameter')
 for key in ['-Dtest_dir=','-Dreport_dir=']:
  values=[a[len(key):] for a in argv if a.startswith(key)]
  if len(values)!=1 or not Path(values[0]).resolve().is_relative_to(out):raise GuardAbort('Generated output outside job')
 if '-seed' in argv or any(a.startswith('-Dseed') for a in argv):raise GuardAbort('Caller must not override locked seed')
 return [*argv,'-seed',str(job['seed'])]

"""Gradle-specific profile/seed guard, E49-identical except build-tool label.
No launcher. A qualified controller must bind CP to the ordered Gradle audit.
"""
from pathlib import Path
from maven_adapter_v1 import R,JDK,WORKSPACE,GuardAbort,new_job_output,reviewer_options

def checked_gradle_generation_argv(argv,job,out):
 out=new_job_output(out);argv=list(map(str,argv))
 if job.get('reused_result') or job.get('status')=='REUSED_VERIFIED_E49':raise GuardAbort('Refuse regeneration of accepted E49')
 if job['build_tool']!='gradle':raise GuardAbort('Gradle adapter cannot admit Maven')
 if job['seed']!=20261023+job['sample_index_1based']:raise GuardAbort('Seed rule changed')
 if not argv or Path(argv[0]).resolve()!=(JDK/'bin/java.exe').resolve():raise GuardAbort('Wrong JVM')
 def one(flag):
  if argv.count(flag)!=1 or argv.index(flag)+1>=len(argv):raise GuardAbort('Missing/duplicate argv key: '+flag)
  return argv[argv.index(flag)+1]
 if Path(one('-jar')).resolve()!=(WORKSPACE/'scripts_v2/evosuite-1.2.0.jar').resolve():raise GuardAbort('Wrong EvoSuite JAR')
 normalized='/'+job['focal_path'].lstrip('/')
 if '/src/main/java/' not in normalized:raise GuardAbort('Unqualified source layout')
 expected_class=normalized.split('/src/main/java/',1)[1].removesuffix('.java').replace('/','.')
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
 i=1
 while i<len(argv):
  if argv[i] in {'-jar','-class','-projectCP'}:i+=2
  elif argv[i].startswith('-D') and argv[i].split('=',1)[0] in allowed:i+=1
  else:raise GuardAbort('Undeclared generation argument')
 return [*argv,'-seed',str(job['seed'])]

"""Read-only validation of an exact Gradle/EvoSuite generation plan.
No command execution, dependency edits, scoring, or benchmark admission.
"""
import json,os
from pathlib import Path
from maven_adapter_v1 import R,sha,generation_bindings
from gradle_command_policy_v2 import ensure,PRIVATE_HOME
from gradle_generation_argv_v1 import checked_gradle_generation_argv
from classpath_transport_v1 import inflate

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def validate(args,job,context,out,lock):
 out=Path(out).resolve();module=(out/'repo'/context['module_dir_relative_to_repo']).resolve()
 attempt=lock.get('generation_attempt');ensure(type(attempt) is int and attempt in {1,2},'Invalid generation attempt')
 transport=lock.get('generation_transport')
 logical=inflate(args,transport,out) if transport is not None else list(args)
 ensure(len(logical)>2 and logical[-2:]==['-seed',str(job['seed'])],'Locked generation seed missing')
 ensure(checked_gradle_generation_argv(logical[:-2],job,out)==logical,'Generation profile or option mismatch')
 for key,expected in [('-Dtest_dir=',module/'src/test/java'),('-Dreport_dir=',module/'evosuite-report')]:
  values=[v[len(key):] for v in logical if v.startswith(key)]
  ensure(len(values)==1 and Path(values[0]).resolve()==expected.resolve(),'Generation output must use exact selected module')
 guard=Path(lock['generation_classpath_guard']).resolve()
 ensure(guard.is_relative_to(out/'classpath_guards') and lock['code_and_input_hashes'].get(str(guard))==sha(guard),'Ordered generation CP guard not pinned')
 rows=load(guard);ensure(isinstance(rows,list) and rows,'Empty generation classpath evidence')
 cp=logical[logical.index('-projectCP')+1]
 ensure(cp.split(os.pathsep)==[r['path'] for r in rows],'Generation classpath order differs from evidence')
 for r in rows:
  p=Path(r['path']).resolve()
  if p.is_dir():
   ensure(p.is_relative_to(out/'repo') and r['kind']=='directory','External/unqualified class directory')
   observed={q.relative_to(p).as_posix():sha(q) for q in p.rglob('*') if q.is_file()}
   ensure(observed==r['files'],'Generation directory bytes drift')
  else:
   ensure(p.is_file() and r['kind']=='file' and sha(p)==r['sha256'],'Missing or altered CP artifact')
   ensure(lock['code_and_input_hashes'].get(str(p))==r['sha256'],'Classpath artifact absent from admitted input pins')
 ensure(any(r['kind']=='directory' for r in rows),'Generation requires compiled main output')
 if attempt==1:
  ensure(lock.get('retry_evidence') is None,'Primary attempt cannot have retry evidence')
 else:
  receipt=Path(lock['retry_evidence']).resolve()
  ensure(receipt==out/'generation_attempts/01/invocation.json' and lock['code_and_input_hashes'].get(str(receipt))==sha(receipt),'Retry lacks pinned primary invocation')
  prior=load(receipt);ensure(prior['attempt']==1 and prior['seed']==job['seed'],'Retry identity changed')
  ensure(not prior['timeout'] and (prior['returncode']!=0 or not prior['native_test_exists']),'Retry after successful generation/timeout forbidden')
  stdout=Path(prior['stdout_path']);stderr=Path(prior['stderr_path'])
  ensure(stdout.is_relative_to(out/'commands') and stderr.is_relative_to(out/'commands'),'Retry output escapes owned command')
  ensure(sha(stdout)==prior['stdout_sha256'] and sha(stderr)==prior['stderr_sha256'],'Primary failure evidence drift')
  helpers=generation_bindings(None,out,lambda *a,**k:None)
  output=stdout.read_text(encoding='utf-8',errors='replace')+'\n'+stderr.read_text(encoding='utf-8',errors='replace')
  ensure(helpers['should_retry_evosuite_with_sanitized_classpath'](output),'No predeclared technical retry marker')
  old=prior['logical_argv'];oldcp=old[old.index('-projectCP')+1]
  sanitized,_=helpers['sanitize_evosuite_generation_classpath'](oldcp.split(os.pathsep))
  ensure(sanitized and cp==os.pathsep.join(sanitized) and cp!=oldcp,'Retry is not exact predeclared sanitizer')
  replaced=list(old);replaced[replaced.index('-projectCP')+1]=cp
  ensure(logical==replaced,'Retry changes more than classpath: seed/profile/budget fixed')
 return logical

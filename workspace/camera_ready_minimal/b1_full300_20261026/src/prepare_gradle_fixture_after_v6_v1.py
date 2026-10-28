"""Prepare one saved-suite synthetic fixture after the current153 invocation.
No Maven/Gradle/Java/EvoSuite/API process runs in this preparation.
"""
import ast,copy,json,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

source=R/'src/queue_gradle_native_after_v5_v1.py'
target=R/'src/queue_gradle_native_after_v6_v1.py'
assert not target.exists()
text=source.read_text(encoding='utf-8').replace('queue_gradle_native_after_v5_v1','queue_gradle_native_after_v6_v1')
text=text.replace('gradle_native_after_v5_v1','gradle_native_after_v6_v1').replace('remaining_maven167_v5','remaining_maven153_v6')
text=text.replace('admission_maven_v5.json','admission_maven_v6.json').replace('B1_GRADLE_V5_','B1_GRADLE_V6_')
text=text.replace('bounded10','current153').replace('BOUNDED10','CURRENT153')
text=text.replace('new bounded10 checkpoint','current153-class invocation')
start=text.index('def eligible(')
end=text.index('def pins_match(',start)
text=text[:start]+'''def eligible(record,expected_plan_hash):
 if not isinstance(record,dict):return False
 if type(record.get('exit_code')) is not int or record['exit_code']!=0:return False
 if type(record.get('jobs_finished_this_invocation')) is not int or record['jobs_finished_this_invocation']!=153:return False
 a,b=record.get('new_scored_this_invocation'),record.get('new_deferred_this_invocation')
 if type(a) is not int or type(b) is not int or min(a,b)<0 or a+b!=153:return False
 if type(record.get('new_policy_accepted')) is not int or record['new_policy_accepted']!=46+a:return False
 deferred=record.get('unscored_deferred_indices')
 if not isinstance(deferred,list) or any(type(i) is not int for i in deferred) or len(set(deferred))!=len(deferred):return False
 fixed={48,49,72,112,119,163,173,211,220,269,275,294}
 if not fixed.issubset(deferred) or len(deferred)!=12+b:return False
 if record['new_policy_accepted']+len(deferred)!=211:return False
 return (record.get('automatic_resume') is False and record.get('error') is None
         and record.get('full300_complete') is False and record.get('Gradle_benchmark_admitted') is False
         and type(record.get('GPT_API_calls')) is int and record['GPT_API_calls']==0
         and record.get('launch_plan_sha256')==expected_plan_hash)
''' +text[end:]
# The writer can publish completion just before unlocking. Do not mistake
# this short interval for permission to start a Java child immediately.
old="   if not pins_match(pins):state('STOPPED_SOURCE_PIN_DRIFT');return 1\n   break"
new="""   if not pins_match(pins):state('STOPPED_SOURCE_PIN_DRIFT');return 1
   with (R/'runtime/dispatcher.lock').open('r+b') as idle:
    try:idle.seek(0);msvcrt.locking(idle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:time.sleep(2);continue
    else:idle.seek(0);msvcrt.locking(idle.fileno(),msvcrt.LK_UNLCK,1)
   break"""
assert text.count(old)==1
text=text.replace(old,new)
text=text.replace('after successful current153 checkpoint only; not full-cohort completion',
                  'after clean completion and dispatcher unlock of current153 Maven invocation; unscored classes remain, NOT Maven260 or full300 completion')
ast.parse(text)
with target.open('x',encoding='utf-8') as f:f.write(text)
ns={'__name__':'b1_v6_queue_pure_guards','__file__':str(target)}
exec(compile(text,str(target),'exec'),ns)
eligible=ns['eligible']
fixed=[48,49,72,112,119,163,173,211,220,269,275,294]
new_deferred=[128,138,145,148,198,202]
base={'exit_code':0,'jobs_finished_this_invocation':153,'new_scored_this_invocation':147,
      'new_deferred_this_invocation':6,'new_policy_accepted':193,
      'unscored_deferred_indices':sorted(fixed+new_deferred),'automatic_resume':False,
      'error':None,'full300_complete':False,'Gradle_benchmark_admitted':False,'GPT_API_calls':0,
      'launch_plan_sha256':'a'*64}
assert eligible(base,'a'*64)
checks=['accept only clean153 completion with exact class accounting211; includes unscored subjects without claiming success']
for key,value in [('exit_code',1),('exit_code',False),('jobs_finished_this_invocation',152),
                  ('new_scored_this_invocation',True),('new_scored_this_invocation',148),
                  ('new_deferred_this_invocation',-1),('new_policy_accepted',192),
                  ('unscored_deferred_indices',fixed),('unscored_deferred_indices',fixed+new_deferred+[202]),
                  ('unscored_deferred_indices',[False]+fixed+new_deferred),
                  ('automatic_resume',True),('error',{'type':'GuardAbort'}),
                  ('full300_complete',True),('Gradle_benchmark_admitted',True),('GPT_API_calls',1),
                  ('launch_plan_sha256','b'*64)]:
    bad=copy.deepcopy(base);bad[key]=value
    assert not eligible(bad,'a'*64)
    checks.append('reject '+key+' mismatch')
assert not eligible({},'a'*64)
checks.append('reject missing completion')
runner=R/'src/run_gradle_native_fixture_v1.py'
prepared=json.loads((R/'validation/gradle_native_fixture_preparation_v1/result.json').read_text(encoding='utf-8'))
assert prepared['status']=='PASS_PREPARATION_ONLY' and prepared['source_sha256']==sha(runner)
assert not (R/'validation/gradle_native_runtime_fixture_v1').exists()
dump(R/'validation/gradle_fixture_after_v6_v1/result.json',{'status':'PASS_PURE_COMPLETION_AND_CLASS_ACCOUNTING_GUARDS',
     'source_sha256':sha(target),'previous_skipped_queue_sha256':sha(source),'checks':checks,
     'fixture_runner_sha256':sha(runner),'maximum_synthetic_fixtures':1,'Gradle_versions':['2.13'],
     'generation_allowed':False,'new_Java_processes':0,'new_EvoSuite_calls':0,'GPT_API_calls':0,
     'Gradle_benchmark_admitted':False,'wait_for_dispatcher_unlock':True,'full300_claim_allowed':False})
audit.log('B1_V6_SINGLE_GRADLE_COMPONENT_QUEUE_PREPARED',source_sha256=sha(target),checks=len(checks),
          maximum_synthetic_fixtures=1,new_Java_processes=0,new_EvoSuite_calls=0,GPT_API_calls=0)
print(json.dumps({'status':'PASS_PURE_PREPARATION','checks':len(checks),'maximum_fixtures':1,'new_processes':0},indent=2))

"""Prepare a one-shot synthetic fixture after the bounded10 checkpoint.
Does not run Gradle, Java, EvoSuite or an API. Old skipped queue stays intact.
"""
import ast, copy, json, sys
from pathlib import Path
from maven_adapter_v1 import R, sha, dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

source=R/'src/queue_gradle_native_after_maven_v1.py'
target=R/'src/queue_gradle_native_after_v5_v1.py'
assert not target.exists()
text=source.read_text(encoding='utf-8')
text=text.replace('Only after successful Maven260 completion: four synthetic measurement fixtures.',
                  'Only after the new bounded10 checkpoint succeeds: one synthetic fixture.\nThis is component qualification during an idle window, not Maven260 completion.')
text=text.replace('queue_gradle_native_after_maven_v1.py','queue_gradle_native_after_v5_v1.py')
text=text.replace('runtime/gradle_native_after_maven_v1','runtime/gradle_native_after_v5_v1')
text=text.replace('remaining_maven198_v1','remaining_maven167_v5')
text=text.replace("VERSIONS=['2.13','5.2.1','6.9.4','8.14.4']","VERSIONS=['2.13']")
start=text.index('def eligible(')
end=text.index('def pins_match(',start)
text=text[:start]+'''def eligible(record,expected_plan_hash):
 return (isinstance(record,dict) and type(record.get('exit_code')) is int and record['exit_code']==0
         and type(record.get('jobs_finished_this_invocation')) is int and record['jobs_finished_this_invocation']==10
         and type(record.get('new_policy_accepted')) is int and 42<=record['new_policy_accepted']<=52
         and record.get('automatic_resume') is False and record.get('error') is None
         and record.get('full300_complete') is False and record.get('Gradle_benchmark_admitted') is False
         and type(record.get('GPT_API_calls')) is int and record['GPT_API_calls']==0
         and record.get('launch_plan_sha256')==expected_plan_hash)
''' +text[end:]
text=text.replace('B1_GRADLE_FIXTURE_CONTINUATION_STATE','B1_GRADLE_V5_SYNTHETIC_CONTINUATION_STATE')
text=text.replace('after successful current Maven invocation only','one Gradle2.13 synthetic measurement fixture after successful bounded10 checkpoint only; not full-cohort completion')
text=text.replace('WAITING_FOR_MAVEN260_SUCCESS','WAITING_FOR_BOUNDED10_CLEAN_COMPLETION')
text=text.replace('SKIPPED_MAVEN_NOT_SUCCESSFULLY_COMPLETE','SKIPPED_BOUNDED10_NOT_CLEANLY_COMPLETE')
text=text.replace('MAVEN_SUCCESS_READY_FOR_SYNTHETIC_FIXTURES','BOUNDED10_CLEAN_COMPONENT_QUALIFICATION_READY')
text=text.replace('FOUR_SYNTHETIC_COMPONENTS_PASSED_NOT_CORPUS_ADMISSION','ONE_SYNTHETIC_COMPONENT_PASSED_NOT_CORPUS_ADMISSION')
text=text.replace('GRADLE_NATIVE_FIXTURES_PASS_GENERATION_ADAPTER_PENDING','GRADLE213_NATIVE_COMPONENT_PASS_OTHER_WRAPPERS_AND_GENERATION_PENDING')
# The fixture itself still checks the old frozen inputs/protocol and has its
# own non-blocking dispatcher lock. The queue pins the new parent admission.
text=text.replace("R/'admission_maven_v3.json'","R/'admission_maven_v5.json'")
assert "VERSIONS=['2.13']" in text and 'remaining_maven198_v1' not in text
ast.parse(text)
with target.open('x',encoding='utf-8') as f:
    f.write(text)
namespace={'__name__':'b1_v5_queue_pure_validation','__file__':str(target)}
exec(compile(text,str(target),'exec'),namespace)
eligible=namespace['eligible']
base={'exit_code':0,'jobs_finished_this_invocation':10,'new_policy_accepted':52,
      'automatic_resume':False,'error':None,'full300_complete':False,
      'Gradle_benchmark_admitted':False,'GPT_API_calls':0,'launch_plan_sha256':'a'*64}
assert eligible(base,'a'*64)
checks=['only matching clean bounded10 completion; no full-Maven claim']
for key,value in [('exit_code',1),('exit_code',False),('jobs_finished_this_invocation',9),
                  ('jobs_finished_this_invocation',True),('new_policy_accepted',53),
                  ('automatic_resume',True),('error',{'type':'GuardAbort'}),('full300_complete',True),
                  ('Gradle_benchmark_admitted',True),('GPT_API_calls',1),('launch_plan_sha256','b'*64)]:
    bad=copy.deepcopy(base)
    bad[key]=value
    assert not eligible(bad,'a'*64)
    checks.append('reject '+key+' mismatch')
assert not eligible({},'a'*64)
checks.append('reject missing completion')
runner=R/'src/run_gradle_native_fixture_v1.py'
prepared=json.loads((R/'validation/gradle_native_fixture_preparation_v1/result.json').read_text(encoding='utf-8'))
assert prepared['status']=='PASS_PREPARATION_ONLY' and prepared['source_sha256']==sha(runner)
assert not (R/'validation/gradle_native_runtime_fixture_v1').exists()
dump(R/'validation/gradle_fixture_after_v5_v1/result.json',{'status':'PASS_PURE_PARENT_DEPENDENCY_GUARDS',
     'source_sha256':sha(target),'original_skipped_queue_source_sha256':sha(source),
     'fixture_runner_sha256':sha(runner),'checks':checks,'Gradle_versions':['2.13'],
     'maximum_synthetic_fixtures':1,'Java_processes_started':0,'new_EvoSuite_calls':0,
     'GPT_API_calls':0,'Gradle_benchmark_admitted':False,'original_queue_modified':False})
audit.log('B1_V5_SINGLE_GRADLE_COMPONENT_QUEUE_PREPARED',source_sha256=sha(target),
          checks=len(checks),versions=['2.13'],new_EvoSuite_calls=0,GPT_API_calls=0)
print('PASS:13 parent-completion guards; one Gradle2.13 synthetic component only; no process launched')

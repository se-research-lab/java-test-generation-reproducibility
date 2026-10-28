"""Explicit one-pass synthetic measurement qualification for remaining wrappers.
No corpus, generator call, scheduler, automatic retry, or configuration repair.
"""
import json,msvcrt,sys
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump,GuardAbort
from run_gradle_native_fixture_v7 import execute_fixture
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'runtime/gradle_fixture_matrix_v7';O.mkdir(exist_ok=False)
versions=['5.2.1','6.9.4','8.14.4'];results=[]
dump(O/'plan.json',{'versions_in_order':versions,'scope':'synthetic native measurement only','script_sha256':sha(__file__),'runner_sha256':sha(R/'src/run_gradle_native_fixture_v7.py'),'recipe_sha256':sha(R/'src/gradle_native_recipe_v7.py'),'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0,'automatic_retry':False})
with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
 mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
 try:
  for version in versions:
   if (R/'STOP_REQUESTED.json').exists():raise GuardAbort('STOP requested; no new qualification process')
   status=json.loads((R/'status.json').read_text(encoding='utf-8'))
   status.update(phase='GRADLE_SYNTHETIC_QUALIFICATION / '+version,updated_utc=datetime.now(timezone.utc).isoformat(),running=0,active_sample_index=None,benchmark_admitted=False)
   status['blockers']=['Đang nghiệm thu adapter bằng fixture; chưa chạy Gradle40','2.13 native measurement PASS; các wrapper khác đang được kiểm lần lượt','20 Maven vẫn deferred/unscored; cấu hình và kết quả cũ giữ nguyên']
   publish_json(R/'status.json',status,label='gradle_fixture_matrix_v7')
   try:execute_fixture(version);state='PASS_SYNTHETIC_NATIVE_MEASUREMENT_ONLY'
   except (Exception,GuardAbort) as ex:
    if (R/'STOP_REQUESTED.json').exists():raise
    state='FAILED_NO_AUTOMATIC_RETRY';dump(O/('failure_'+version+'.json'),{'error_type':type(ex).__name__,'detail':str(ex),'automatic_retry':False})
   results.append({'version':version,'state':state});publish_json(O/'state.json',{'results':results,'current_version':None,'benchmark_admitted':False},label='gradle_matrix_state')
   print(json.dumps(results[-1]),flush=True)
  dump(O/'complete.json',{'status':'COMPLETE_SYNTHETIC_MATRIX_ONLY','results':results,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0})
  audit.log('B1_GRADLE_FIXTURE_MATRIX_V7_COMPLETE',completion_sha256=sha(O/'complete.json'),new_EvoSuite_calls=0,GPT_API_calls=0)
 finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

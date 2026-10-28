"""Pure negative tests for dependent-stage admission; no process launched."""
import copy,sys
from maven_adapter_v1 import R,sha,dump
from queue_gradle_native_after_maven_v1 import eligible
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
base={'exit_code':0,'Maven260_terminal':True,'new_policy_accepted':211,'automatic_resume':False,'launch_plan_sha256':'a'*64};checks=[]
assert eligible(base,'a'*64);checks.append('only complete successful211newMaven record admits dependent qualification')
for field,value in [('exit_code',1),('exit_code',False),('Maven260_terminal',False),('new_policy_accepted',210),('new_policy_accepted',True),('automatic_resume',True),('launch_plan_sha256','b'*64)]:
 test=copy.deepcopy(base);test[field]=value;assert not eligible(test,'a'*64);checks.append('reject '+field+' mismatch')
assert not eligible({},'a'*64);checks.append('missing completion cannot admit fixture')
source=R/'src/queue_gradle_native_after_maven_v1.py'
dump(R/'validation/gradle_fixture_continuation_v1/result.json',{'status':'PASS_PURE_DEPENDENCY_GUARDS','checks':checks,'source_sha256':sha(source),'processes_started':0,'GPT_API_calls':0,'new_EvoSuite_calls':0,'Gradle_benchmark_admitted':False})
audit.log('B1_GRADLE_FIXTURE_CONTINUATION_GUARDS_VALIDATED',source_sha256=sha(source),checks=len(checks),processes_started=0);print('PASS: '+str(len(checks))+' dependency guard checks; no process launched')

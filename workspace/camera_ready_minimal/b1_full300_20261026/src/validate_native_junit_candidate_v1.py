import json,sys
from pathlib import Path
from native_junit_policy_candidate_v1 import candidate,compare,GuardAbort
from maven_adapter_v1 import R,dump,sha
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
base='<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion></project>'
empty={'classpath':[],'compile_classpath':[]};tests=[]
new,changed=candidate(base,empty);assert changed and '<scope>test</scope>' in new;tests.append('only missing dependency supplied at test scope')
junit={'path':'junit/junit/4.13.2/junit-4.13.2.jar','sha256':'j'}
assert candidate(new,{'classpath':[junit]})==(new,False);tests.append('idempotent with resolved JUnit4')
try:candidate(new,empty);raise AssertionError('did not reject unresolved declaration')
except GuardAbort:tests.append('unresolved declaration rejected')
try:candidate(base,{'classpath':[{'path':'junit/junit/3.8.1/junit-3.8.1.jar'}]});raise AssertionError('did not reject JUnit3')
except GuardAbort:tests.append('JUnit3 not silently upgraded')
assert compare(empty,{'classpath':[junit],'compile_classpath':[]})['production_compile_closure']=='UNCHANGED';tests.append('test-only delta accepted')
for case in [{'classpath':[junit],'compile_classpath':[junit]},{'classpath':[junit,{'path':'other.jar','sha256':'x'}],'compile_classpath':[]}]:
 try:compare(empty,case);raise AssertionError('unsafe delta accepted')
 except GuardAbort:tests.append('unsafe dependency delta rejected')
rows=[]
for i in range(1,50):
 p=B/'e49_measurement_compat_v1/jobs'/f'{i:02d}'/'before_dependency.json';d=json.loads(p.read_text(encoding='utf-8'))
 assert candidate(base,d)==(base,False);rows.append({'job_index':i,'dependency_sha256':sha(p),'would_change':False})
out=R/'validation/native_junit_candidate_v1/result.json';dump(out,{'status':'PASS','checks':tests,'accepted49_predicate_check':rows,'runtime_qualified':False,'benchmark_admitted':False,'new_experiment_calls':0});audit.log('B1_NATIVE_JUNIT_CANDIDATE_STATIC_VALIDATED',result_sha256=sha(out),accepted49_noop=49);print('PASS: 7 static checks; accepted49 predicate unchanged; runtime not qualified')

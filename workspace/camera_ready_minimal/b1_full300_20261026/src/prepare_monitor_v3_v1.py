"""Prepare read-only monitor liveness checking. No server/process launched."""
import ast, copy, sys
from maven_adapter_v1 import R, sha, dump
from preview_runner_health_v1 import same_identity, EXPECTED
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

source=R/'monitor/serve_v2.py'
target=R/'monitor/serve_v3.py'
text=source.read_text(encoding='utf-8')
old="R=Path(__file__).resolve().parents[1]"
assert text.count(old)==1
text=text.replace(old,old+"\nsys.path.insert(0,str(R/'src'))\nfrom preview_runner_health_v1 import view_status")
old="content=(R/'status.json').read_bytes();kind='application/json; charset=utf-8'"
assert text.count(old)==1
text=text.replace(old,"content=json.dumps(view_status(json.loads((R/'status.json').read_text(encoding='utf-8'))),ensure_ascii=False).encode('utf-8');kind='application/json; charset=utf-8'")
ast.parse(text)
with target.open('x',encoding='utf-8') as f:
    f.write(text)
identity={'pid':1234,'create_time':100.5,'script':str(EXPECTED)}
assert same_identity(identity,100.5,[str(EXPECTED)])
checks=['match PID metadata, creation time and exact admitted script']
for label,key,value in [('reject bool PID','pid',True),('reject nonpositive PID','pid',0),
                         ('reject foreign script','script',str(R/'src/run_maven_b1_v3.py')),
                         ('reject creation-time mismatch','create_time',101)]:
    bad=copy.deepcopy(identity)
    bad[key]=value
    assert not same_identity(bad,100.5,[str(EXPECTED)])
    checks.append(label)
assert not same_identity(identity,100.5,[str(R/'src/run_maven_b1_v3.py')])
checks.append('reject reused PID with different process command')
dump(R/'validation/monitor_v3_preparation_v1/result.json',{'status':'PASS_PURE_HEALTH_GUARDS_NO_SERVER_STARTED',
     'checks':checks,'prior_server_sha256':sha(source),'server_sha256':sha(target),
     'health_source_sha256':sha(R/'src/preview_runner_health_v1.py'),'new_experiments':0,'GPT_API_calls':0,
     'original_server_modified':False,'render_QA_performed':False})
audit.log('B1_MONITOR_V3_PREPARED_READONLY_HEALTH',server_sha256=sha(target),checks=len(checks),new_experiments=0)
print('PASS: monitor v3 prepared;6 pure liveness guards; no server/experiment started')

"""Keep old monitors; add display support for admitted v6 without experiments."""
import ast,copy,sys
from maven_adapter_v1 import R,sha,dump
from preview_runner_health_v2 import same_owner
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

source=R/'monitor/serve_v3.py'
target=R/'monitor/serve_v4.py'
text=source.read_text(encoding='utf-8')
assert text.count('from preview_runner_health_v1 import view_status')==1
text=text.replace('from preview_runner_health_v1 import view_status','from preview_runner_health_v2 import view_status')
ast.parse(text)
with target.open('x',encoding='utf-8') as f:
    f.write(text)
expected=R/'src/run_remaining_maven153_v6.py'
identity={'pid':1234,'create_time':42.5,'script':str(expected)}
assert same_owner(identity,42.5,[str(expected)],expected)
checks=['exact allowed v6 owner match']
for label,key,value in [('bool pid','pid',True),('nonpositive pid','pid',0),('reused pid creation','create_time',1),
                         ('foreign owner script','script',str(R/'src/run_maven_b1_v3.py'))]:
    row=copy.deepcopy(identity)
    row[key]=value
    assert not same_owner(row,42.5,[str(expected)],expected)
    checks.append('reject '+label)
assert not same_owner(identity,42.5,[str(R/'src/run_remaining_maven167_v5.py')],expected)
checks.append('reject different command')
dump(R/'validation/monitor_v4_preparation_v1/result.json',{'status':'PASS_DISPLAY_ONLY_OWNER_GUARDS',
     'checks':checks,'old_server_sha256':sha(source),'server_sha256':sha(target),
     'helper_sha256':sha(R/'src/preview_runner_health_v2.py'),'new_experiment_calls':0,'GPT_API_calls':0})
audit.log('B1_MONITOR_V4_PREPARED_V5_V6_OWNERS',server_sha256=sha(target),checks=len(checks),new_experiments=0)
print('PASS: display-only v4;6 owner checks; no processes launched')

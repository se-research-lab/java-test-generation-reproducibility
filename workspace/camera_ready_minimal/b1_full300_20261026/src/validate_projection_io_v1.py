"""Meaningful mocked Windows sharing failures; no Java or benchmark execution."""
import json,os,sys,time
from pathlib import Path
from projection_io_v1 import R,IO_ROOT,publish_json,GuardAbort,digest
from maven_adapter_v1 import dump,sha
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'validation/projection_io_v1';O.mkdir(parents=True,exist_ok=False)
T=R/'runtime/projection_io_validation_v1';T.mkdir(exist_ok=False);checks=[]

first=T/'transient.json';old=b'{"old":"byte exact"}\r\n';first.write_bytes(old);attempts=[]
def transient(source,target):
 attempts.append(str(source))
 if len(attempts)<=2:raise PermissionError(13,'mock Win5 reader-sharing conflict')
 os.replace(source,target)
r=publish_json(first,{'new':[1,'kiểm tra']},label='test_transient',max_retry_seconds=.3,retry_delay_seconds=.01,replace_fn=transient)
assert r['published'] and r['attempts']==3 and json.loads(first.read_text(encoding='utf-8'))=={'new':[1,'kiểm tra']}
assert Path(r['backup']['path']).read_bytes()==old and r['backup']['sha256']==digest(old)
checks.append('transient PermissionError retries then publishes; prior bytes/hash retained')

second=T/'persistent.json';second.write_bytes(old)
def persistent(source,target):raise PermissionError(13,'mock persistent Win5')
start=time.monotonic();r2=publish_json(second,{'after':True},label='test_persistent',max_retry_seconds=.08,retry_delay_seconds=.02,replace_fn=persistent);elapsed=time.monotonic()-start
assert not r2['published'] and r2['error_type']=='PermissionError' and elapsed<2 and second.read_bytes()==old
assert r2['temporary_preserved'] and Path(r2['temporary_path']).is_file() and Path(r2['receipt_path']).is_file()
checks.append('persistent sharing failure is bounded and returns report; old target and failed temp remain')
r3=publish_json(second,{'after':'other'},label='test_persistent',max_retry_seconds=.03,retry_delay_seconds=.01,replace_fn=persistent)
assert r2['temporary_path']!=r3['temporary_path'] and Path(r2['temporary_path']).is_file() and Path(r3['temporary_path']).is_file()
checks.append('successive failures use distinct exclusive temp names and preserve both')

third=T/'disk_error.json';third.write_bytes(old)
def disk_error(source,target):raise OSError(28,'mock disk full on replace')
r4=publish_json(third,{'after':3},label='test_disk_error',replace_fn=disk_error)
assert not r4['published'] and r4['attempts']==1 and r4['error_type']=='OSError' and third.read_bytes()==old
checks.append('other OSError returns failure immediately without retry or experiment exception')

for data,error in [({'bad':float('nan')},ValueError),({'bad':object()},TypeError),({1:'non-string key'},TypeError)]:
 before=set((IO_ROOT/'temporary').iterdir())
 try:publish_json(T/'invalid.json',data,label='test_invalid');raise AssertionError('invalid data accepted')
 except error:pass
 assert set((IO_ROOT/'temporary').iterdir())==before
checks.append('invalid JSON data propagates and creates no temporary files')
outside=R/'forbidden_ui_projection_test.json'
try:publish_json(outside,{'x':1});raise AssertionError('outside target accepted')
except GuardAbort:pass
assert not outside.exists();checks.append('outside runtime/status target rejected with GuardAbort')
def guard_abort(source,target):raise GuardAbort('mock integrity abort')
try:publish_json(T/'guard.json',{'x':1},label='test_guard_abort',replace_fn=guard_abort);raise AssertionError('GuardAbort swallowed')
except GuardAbort:pass
checks.append('GuardAbort from replacement boundary is not swallowed')

report={'status':'PASS_STATIC_MOCKED_IO_ONLY','checks':checks,'sharing_failure_max_elapsed_seconds':elapsed,'processes_started':0,'Java_Gradle_EvoSuite_calls':0,'GPT_API_calls':0,'raw_benchmark_results_modified':False,'source_sha256':sha(R/'src/projection_io_v1.py'),'validator_sha256':sha(__file__),'receipt_examples':[r,r2,r3,r4]}
dump(O/'result.json',report);audit.log('B1_PROJECTION_IO_V1_STATIC_VALIDATED',result_sha256=sha(O/'result.json'),checks=len(checks),new_experiment_calls=0)
print(json.dumps({k:v for k,v in report.items() if k!='receipt_examples'},ensure_ascii=False,indent=2))

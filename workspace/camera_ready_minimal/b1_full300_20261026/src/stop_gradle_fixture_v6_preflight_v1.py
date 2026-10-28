"""Stop only the identified synthetic preflight, only before any Java/command.
Preserve all evidence and leave the audited parent wrapper to record exit.
"""
import json,sys,time
from datetime import datetime,timezone
import psutil
from maven_adapter_v1 import R,sha,dump,GuardAbort
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
expected=R/'src/run_gradle_native_fixture_v6.py';out=R/'validation/gradle_native_runtime_fixture_v6/gradle_2.13'
p=psutil.Process(5268)
assert abs(p.create_time()-1793046256.7742608)<.01
assert str(expected) in p.cmdline() and '--version' in p.cmdline() and p.cmdline()[-1]=='2.13'
assert not out.exists() and not p.children(recursive=True),'Fixture has entered execution; preflight-only stop refused'
record={'at_utc':datetime.now(timezone.utc).isoformat(),'pid':p.pid,'create_time':p.create_time(),'script':str(expected),'script_sha256':sha(expected),'reason':'Replace sequential full-file SHA256 checking with equivalent bounded parallel reads; no experimental command was started','out_directory_absent':True,'observed_descendants':[],'io_before':p.io_counters()._asdict(),'cpu_before':list(p.cpu_times())[:2],'auto_restart':False,'new_Java_calls':0,'new_EvoSuite_calls':0,'GPT_API_calls':0}
p.suspend()
try:
 assert abs(p.create_time()-record['create_time'])<.01 and not p.children(recursive=True) and not out.exists(),'Race detected; no termination'
 p.terminate();record['exit_code']=p.wait(timeout=15)
finally:
 if p.is_running():p.resume()
dump(R/'runtime/gradle_fixture_v6_preflight_stop.json',record)
audit.log('B1_GRADLE_SYNTHETIC_PREFLIGHT_STOPPED',receipt_sha256=sha(R/'runtime/gradle_fixture_v6_preflight_stop.json'),pid=record['pid'],create_time=record['create_time'],Java_calls=0,EvoSuite_calls=0)
print(json.dumps(record,indent=2))

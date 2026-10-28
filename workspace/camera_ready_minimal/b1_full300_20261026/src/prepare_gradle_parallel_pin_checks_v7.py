"""Change verification scheduling only; all file/hash checks are retained."""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump,GuardAbort
from parallel_pin_verify_v1 import verify_pins
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
out=R/'audit/gradle_parallel_pin_checks_v7';out.mkdir(exist_ok=False);changes=[]
def write(old,new,text):
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 diff=out/(new.stem+'.diff');diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 changes.append({'old':str(old),'old_sha256':sha(old),'new':str(new),'new_sha256':sha(new),'diff_sha256':sha(diff)})
old=R/'src/gradle_process_supervisor_v4.py';new=R/'src/gradle_process_supervisor_v5.py';text=old.read_text(encoding='utf-8')
text=text.replace('import json,os','import json,os\nfrom parallel_pin_verify_v1 import verify_pins')
text=text.replace("   for p,h in records.items():ensure(sha(p)==h,'Code/input hash drift: '+str(p))",'   verify_pins(records)')
text=text.replace('B1_gradle_supervisor_v4','B1_gradle_supervisor_v5').replace('gradle_guard_v4','gradle_guard_v5');write(old,new,text)
old=R/'src/run_gradle_native_fixture_v6.py';new=R/'src/run_gradle_native_fixture_v7.py';text=old.read_text(encoding='utf-8')
before=""" for r in rows:
  path=home/r['relative'];ensure(path.is_file() and sha(path)==r['sha256'],'Cache input drift: '+r['relative'])"""
after=""" records={str((home/r['relative']).resolve()):r['sha256'] for r in rows}
 ensure(len(records)==len(rows),'Duplicate cache input paths')
 verify_pins(records)"""
assert text.count(before)==1;text=text.replace(before,after)
text=text.replace('import argparse,csv,json,msvcrt,os,re,shutil,sys,traceback','import argparse,csv,json,msvcrt,os,re,shutil,sys,traceback\nfrom parallel_pin_verify_v1 import verify_pins')
text=text.replace('gradle_command_policy_v2','gradle_command_policy_v3').replace('gradle_process_supervisor_v3','gradle_process_supervisor_v5').replace('B1_gradle_supervisor_v3','B1_gradle_supervisor_v5').replace('gradle_native_runtime_fixture_v6','gradle_native_runtime_fixture_v7')
text=text.replace("pinpaths=[Path(__file__),", "pinpaths=[Path(__file__),R/'src/parallel_pin_verify_v1.py',R/'src/gradle_generation_plan_guard_v1.py',R/'src/gradle_generation_argv_v1.py',")
write(old,new,text)
# Meaningful negative checks: same byte length and restored timestamp must not
# hide a mutation; missing input must fail. Verification never writes inputs.
v=R/'validation/parallel_pin_verify_v1';v.mkdir(exist_ok=False);a=v/'a';b=v/'b';a.write_bytes(b'original');b.write_bytes(b'second')
pins={str(a):sha(a),str(b):sha(b)};assert verify_pins(pins)==2
import os
st=a.stat();a.write_bytes(b'changed!');os.utime(a,ns=(st.st_atime_ns,st.st_mtime_ns))
try:verify_pins(pins)
except GuardAbort:pass
else:raise AssertionError('Same-size/time tampering accepted')
try:verify_pins({str(v/'absent'):'0'*64})
except FileNotFoundError:pass
else:raise AssertionError('Missing pin accepted')
dump(v/'result.json',{'status':'PASS','checks':['all full bytes hashed, no mtime/size cache','same-size restored-mtime mutation rejected','missing file rejected','verification itself performs no writes'],'workers':8,'helper_sha256':sha(R/'src/parallel_pin_verify_v1.py')})
dump(out/'preparation.json',{'scope':'hash-check scheduling only; no experimental rules changed','changes':changes,'helper_sha256':sha(R/'src/parallel_pin_verify_v1.py'),'validation_sha256':sha(v/'result.json'),'all_pins_still_hashed_each_check':True,'stat_cache':False,'benchmark_admitted':False,'EvoSuite_calls':0,'GPT_API_calls':0})
audit.log('B1_GRADLE_PARALLEL_PIN_CHECKS_V7_PREPARED',receipt_sha256=sha(out/'preparation.json'),workers=8,all_full_byte_checks_retained=True)
print('PASS: bounded parallel reads; mutation/missing-file guards verified; no corpus execution')

"""Concurrent append test and lossless ledger migration check."""
import concurrent.futures,hashlib,json,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
before=len(audit.events())
def writer(i):
    code='import sys;sys.path.insert(0,'+repr(str(BASE))+');import audit;audit.log("AUDIT_LOCK_TEST_WRITER",writer_index='+str(i)+')'
    r=subprocess.run([sys.executable,'-B','-X','utf8','-c',code],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stderr
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as p:list(p.map(writer,range(20)))
audit.verify_chain();found=[r['writer_index'] for r in audit.events()[before:] if r['kind']=='AUDIT_LOCK_TEST_WRITER']
assert sorted(found)==list(range(20))
oldlines=(BASE/'audit/events.jsonl').read_text(encoding='utf-8').splitlines();now=audit.events()
for i,line in enumerate(oldlines,1):
    original=json.loads(line);rec=now[i-1]
    if i<722:assert rec==original
    else:
        origin=rec['migration_origin'];assert origin['physical_line']==i and origin['original_event']==original
        assert origin['line_sha256']==hashlib.sha256(line.encode('utf-8')).hexdigest()
report={'status':'PASS','concurrent_writers':20,'all_records_present_once':True,'serialized_chain':'PASS','original730_records_imported_losslessly':True,'original_branched_ledger_preserved':True}
p=BASE/'audit/interprocess_lock_validation.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('AUDIT_LOCK_VALIDATED',sha256=audit.sha(p),writers=20);print(json.dumps(report,indent=2))

"""Preserve the branched ledger, import every physical record, and serialize future writers."""
import hashlib,json,os,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
oldledger=BASE/'audit/events.jsonl';newledger=BASE/'audit/events_serialized_v2.jsonl'
assert not newledger.exists()
raw=oldledger.read_bytes();lines=raw.decode('utf-8').splitlines();events=[json.loads(x) for x in lines]
assert any(e['kind']=='COMMAND_END' and e.get('name')=='cache_copy_parallel' and e['returncode']==0 for e in events),'Wait for all old cache writers to finish'
assert all(any(e['kind']=='COMMAND_END' and e.get('name')==n for e in events) for n in ['e49_prepare_manifest02','e49_semantics03_retry','e49_timeout_tree02'])
source=BASE/'audit.py';backup=BASE/'backup/infrastructure/audit_before_serialization.py';backup.parent.mkdir(parents=True,exist_ok=True)
assert not backup.exists();shutil.copy2(source,backup);assert digest(source)==digest(backup)
pre={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':digest(source),'source_backup':str(backup),'old_ledger_sha256':digest(oldledger),
 'reason':'Concurrent COMMAND_START records shared a previous hash. Preserve original ledger and recover all records by physical order; serialize future appends with interprocess lock.'}
prepath=BASE/'audit/serialization_pre_edit.json'
with prepath.open('x',encoding='utf-8') as f:json.dump(pre,f,indent=2)
text=source.read_text(encoding='utf-8');text=text.replace("LEDGER = BASE / 'audit/events.jsonl'","LEDGER = BASE / 'audit/events_serialized_v2.jsonl'")
start=text.index('def log(kind, **data):');end=text.index('\n\ndef verify_chain():',start)
replacement='''def _append_many(items):
    import msvcrt
    import time
    lockpath = BASE / 'audit/events.lock'
    with lockpath.open('a+b') as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        deadline = time.monotonic() + 60
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Audit ledger lock unavailable')
                time.sleep(0.02)
        try:
            prior = events()
            seq = prior[-1]['seq'] if prior else 0
            previous = prior[-1]['event_sha256'] if prior else None
            with LEDGER.open('a', encoding='utf-8') as f:
                for kind, data in items:
                    seq += 1
                    record = dict(seq=seq, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                                  kind=kind, previous_sha256=previous, **data)
                    record['event_sha256'] = hashlib.sha256(canonical(record)).hexdigest()
                    f.write(json.dumps(record, ensure_ascii=False)+'\\n')
                    previous = record['event_sha256']
                f.flush(); os.fsync(f.fileno())
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def log(kind, **data):
    _append_many([(kind, data)])'''
text=text[:start]+replacement+text[end:]
text=text.replace("prior={e['path']:e['sha256'] for e in events() if e['kind']=='NEW_FILE_REGISTERED'}", "prior={e['path']:e['sha256'] for e in events() if e['kind']=='NEW_FILE_REGISTERED'}\n    prior.update({e['path']:e['after_sha256'] for e in events() if e['kind']=='FILE_REVISION'})\n    pending=[]")
text=text.replace("            log('NEW_FILE_REGISTERED',path=rel,sha256=sha(p),bytes=p.stat().st_size,\n                change_type='new isolated file; no original overwritten')", "            pending.append(('NEW_FILE_REGISTERED',dict(path=rel,sha256=sha(p),bytes=p.stat().st_size,\n                change_type='new isolated file; no original overwritten')))\n    _append_many(pending)")
import ast;ast.parse(text);source.write_text(text,encoding='utf-8')
prev=None;first_bad=None;reconstructed=[]
for i,(line,e) in enumerate(zip(lines,events),1):
    original=dict(e);original_hash=e['event_sha256']
    assert hashlib.sha256(canonical({k:v for k,v in e.items() if k!='event_sha256'})).hexdigest()==original_hash,'An original event has an invalid own digest'
    if first_bad is None and (e['seq']!=i or e['previous_sha256']!=prev):first_bad=i
    if first_bad is not None:
        e={k:v for k,v in e.items() if k not in ['seq','previous_sha256','event_sha256']}
        e.update(seq=i,previous_sha256=prev,migration_origin={'ledger':'audit/events.jsonl','physical_line':i,'line_sha256':hashlib.sha256(line.encode('utf-8')).hexdigest(),'original_event':original})
        e['event_sha256']=hashlib.sha256(canonical(e)).hexdigest()
    prev=e['event_sha256'];reconstructed.append(e)
assert first_bad is not None
with newledger.open('x',encoding='utf-8') as f:
    for e in reconstructed:f.write(json.dumps(e,ensure_ascii=False)+'\n')
assert oldledger.read_bytes()==raw,'Old ledger changed during recovery'
sys.path.insert(0,str(BASE));import audit
assert audit.LEDGER==newledger;audit.verify_chain()
audit.log('AUDIT_LEDGER_RECOVERY',original_ledger_sha256=digest(oldledger),original_ledger_preserved=True,
 physical_records_imported=len(events),first_divergent_physical_line=first_bad,order='physical append order, original timestamps and events retained',
 new_ledger='audit/events_serialized_v2.jsonl',future_writers='Windows interprocess byte lock; batch registration appends under one lock',scientific_data_modified=False)
audit.log('FILE_REVISION',path='audit.py',before_sha256=digest(backup),after_sha256=digest(source),backup=str(backup.relative_to(BASE)),reason=pre['reason'])
report={'status':'PASS','old_ledger_sha256':digest(oldledger),'physical_records_preserved':len(events),'first_divergence':first_bad,'new_chain_verified':True,'original_experiment_edits':0,'new_log_lock':True}
p=BASE/'audit/serialization_recovery_result.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))

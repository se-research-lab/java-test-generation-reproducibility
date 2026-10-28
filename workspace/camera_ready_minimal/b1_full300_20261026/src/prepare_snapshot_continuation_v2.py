"""Explicitly reconcile a technical metadata stop; never resumes experimental jobs."""
import json,sqlite3,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'inputs/snapshot_v1';interrupted=json.loads((old/'interrupted.json').read_text());stop=R/'STOP_REQUESTED.json';request=json.loads(stop.read_text())
assert request['requested_by']=='assistant executing authorized B1 preparation' and request['scope']=='B1 source snapshot only; no benchmark active'
assert request['reason'].startswith('Technical pause: replace repeated per-file ancestor traversal')
assert interrupted['completed_roots']==7 and not interrupted['auto_resume']
assert json.loads((R/'validation/snapshot_reader_v2/result.json').read_text())['status']=='PASS'
with sqlite3.connect((old/'content.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
 assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 for p in sorted((old/'checkpoints').glob('*.json')):
  x=json.loads(p.read_text());assert audit.sha(R/x['manifest'])==x['sha256']
record={'reason':request,'previous_interruption':interrupted,'old_store_sha256':audit.sha(old/'content.sqlite3'),'v1_code_sha256':audit.sha(R/'src/freeze_sources_v1.py'),'v2_reader_sha256':audit.sha(R/'src/snapshot_reader_v2.py'),'committed_roots_reused':7,'new_experiment_calls':0,'explicit_technical_continuation':True}
text=(R/'src/freeze_sources_v1.py').read_text(encoding='utf-8')
def replace(a,b):
 global text
 assert a in text,a;text=text.replace(a,b)
replace('from snapshot_store_v1 import *','from snapshot_store_v1 import *\nfrom snapshot_reader_v2 import SourceReader\nimport sqlite3')
replace('status_snapshots_v1','status_snapshots_v2');replace('status.snapshot_v1.tmp','status.snapshot_v2.tmp')
replace("S=R/'inputs/snapshot_v1'","S=R/'inputs/snapshot_v2'")
replace("dump(S/'protocol.json',protocol);c=open_new_store(S/'content.sqlite3');index=[];total=0;status(0,0);event('SNAPSHOT_START',protocol_sha256=audit.sha(S/'protocol.json'),n=251)","""protocol['reader_v2_sha256']=audit.sha(R/'src/snapshot_reader_v2.py')
protocol['explicit_continuation_record_sha256']=audit.sha(R/'audit/snapshot_continuation_v2.json')
protocol['prior_committed_roots']=7
dump(S/'protocol.json',protocol)
with (S/'content.sqlite3').open('xb'):pass
c=sqlite3.connect(S/'content.sqlite3')
with sqlite3.connect((R/'inputs/snapshot_v1/content.sqlite3').as_uri()+'?mode=ro',uri=True) as prior:prior.backup(c)
index=[];total=0;status(0,0);event('SNAPSHOT_V2_START',protocol_sha256=audit.sha(S/'protocol.json'),n=251)""")
replace("  root=Path(item['source_repo']);expected={f['path'] for f in item['files']}","""  if n<=7:
   previous=load(R/'inputs/snapshot_v1/checkpoints'/f'{n:03d}.json');payload=load(R/previous['manifest'])
   assert audit.sha(R/previous['manifest'])==previous['sha256'] and payload['source_repo']==item['source_repo']
   path=S/'manifests'/f'{n:03d}.json';dump(path,payload)
   entry={**previous,'manifest':path.relative_to(R).as_posix(),'sha256':audit.sha(path),'reused_committed_snapshot_v1':True}
   index.append(entry);total+=entry['files'];dump(S/'checkpoints'/f'{n:03d}.json',entry);status(n,total);event('SNAPSHOT_REUSED_COMMITTED_INPUT',**entry);continue
  root=Path(item['source_repo']);expected={f['path'] for f in item['files']}""")
replace('  rows=[];tick=time.monotonic()','  rows=[];tick=time.monotonic();reader=SourceReader(root,c)')
replace("   stopped();rows.append(capture_file(c,root,f['path'],f['bytes'],descriptor_hashes.get(f['path'])))","   if k%100==1:stopped()\n   rows.append(reader.capture(f['path'],f['bytes'],descriptor_hashes.get(f['path'])))")
replace("  settings=root.parent.parent/'settings.xml'","  reader.validate_directories()\n  settings=root.parent.parent/'settings.xml'")
replace("protocol['snapshot_code_sha256']", "protocol['snapshot_code_sha256']") if False else None
target=R/'src/freeze_sources_v2.py'
with target.open('x',encoding='utf-8') as f:f.write(text)
record['v2_driver_sha256']=audit.sha(target)
with (R/'audit/snapshot_continuation_v2.json').open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
dest=R/'backups/STOP_snapshot_technical_v1.json';assert not dest.exists();stop.rename(dest)
audit.log('B1_SNAPSHOT_EXPLICIT_TECHNICAL_CONTINUATION',record_sha256=audit.sha(R/'audit/snapshot_continuation_v2.json'),v1_evidence_preserved=True,committed_roots=7,new_experiment_calls=0)
print(json.dumps(record,ensure_ascii=False,indent=2))

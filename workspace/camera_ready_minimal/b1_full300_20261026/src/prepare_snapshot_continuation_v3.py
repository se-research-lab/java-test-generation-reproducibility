import json,sqlite3,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'inputs/snapshot_v2';interrupted=json.loads((old/'interrupted.json').read_text());n=interrupted['completed_roots']
stop=R/'STOP_REQUESTED.json';request=json.loads(stop.read_text());assert request['requested_by']=='assistant executing authorized B1 preparation' and request['reason'].startswith('Technical pause: enable bounded eight-worker')
assert json.loads((R/'validation/snapshot_reader_v3/result.json').read_text())['status']=='PASS'
assert not (old/'complete.json').exists() and n==len(list((old/'checkpoints').glob('*.json')))
with sqlite3.connect((old/'content.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
text=(R/'src/freeze_sources_v2.py').read_text(encoding='utf-8')
text=text.replace('from snapshot_reader_v2 import SourceReader','from snapshot_reader_v3 import capture_many')
text=text.replace('status_snapshots_v2','status_snapshots_v3').replace('status.snapshot_v2.tmp','status.snapshot_v3.tmp')
text=text.replace("S=R/'inputs/snapshot_v2'","S=R/'inputs/snapshot_v3'")
text=text.replace('snapshot_reader_v2.py','snapshot_reader_v3.py').replace('reader_v2_sha256','reader_v3_sha256').replace('snapshot_continuation_v2.json','snapshot_continuation_v3.json')
text=text.replace("protocol['prior_committed_roots']=7",f"protocol['prior_committed_roots']={n}\nprotocol['source_read_workers']=8\nprotocol['benchmark_workers']=1")
text=text.replace('inputs/snapshot_v1','inputs/snapshot_v2').replace('SNAPSHOT_V2_START','SNAPSHOT_V3_START').replace('reused_committed_snapshot_v1','reused_committed_snapshot_v2').replace('if n<=7:',f'if n<={n}:')
start=text.index('  rows=[];tick=time.monotonic();reader=SourceReader(root,c)');end=text.index('  keyrows=',start)
text=text[:start]+"""  def progress(done,total):
   if done%1024==0 or done==total:print(json.dumps({'phase':'snapshot_reading','root':n,'of':251,'files':done,'root_files':total,'new_experiment_calls':0}),flush=True)
  rows=capture_many(root,c,item['files'],descriptor_hashes,stopped,progress,workers=8)
"""+text[end:]
text=text.replace('  reader.validate_directories()\n','')
target=R/'src/freeze_sources_v3.py'
with target.open('x',encoding='utf-8') as f:f.write(text)
record={'previous_interruption':interrupted,'request':request,'old_store_sha256':audit.sha(old/'content.sqlite3'),'committed_roots_reused':n,'source_read_workers':8,'benchmark_workers':1,'driver_sha256':audit.sha(target),'reader_sha256':audit.sha(R/'src/snapshot_reader_v3.py'),'experimental_calls':0}
with (R/'audit/snapshot_continuation_v3.json').open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
dest=R/'backups/STOP_snapshot_technical_v2.json';assert not dest.exists();stop.rename(dest)
audit.log('B1_SNAPSHOT_EXPLICIT_CONTINUATION_V3',record_sha256=audit.sha(R/'audit/snapshot_continuation_v3.json'),reused_roots=n,read_workers=8,experiment_calls=0)
print(json.dumps(record,ensure_ascii=False,indent=2))

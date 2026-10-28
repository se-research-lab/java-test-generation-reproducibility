"""Freeze 251 prepared source inputs into a private deduplicated byte store."""
import json,sys,shutil,os,time
from pathlib import Path
from datetime import datetime,timezone
from snapshot_store_v1 import *
from snapshot_reader_v2 import SourceReader
import sqlite3
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,data):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def now():return datetime.now(timezone.utc).isoformat()
def event(kind,**data):
 with (R/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'timestamp_utc':now(),'kind':kind,**data},ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 audit.log('B1_'+kind,**data)
def status(n,files):
 old=R/'status.json';p=R/'backups/status_snapshots_v2'/f'{n:03d}.json';p.parent.mkdir(parents=True,exist_ok=True)
 with old.open('rb') as f,p.open('xb') as out:shutil.copyfileobj(f,out)
 s=load(old);s.update(updated_utc=now(),phase=f'SOURCE SNAPSHOT {n}/251',source_snapshot_roots_completed=n,source_snapshot_files=files,disk_free_GB=round(shutil.disk_usage(R).free/1e9,2))
 tmp=R/'status.snapshot_v2.tmp';dump(tmp,s);tmp.replace(old)
def stopped():
 if (R/'STOP_REQUESTED.json').exists():raise IntegrityError('Explicit B1 stop request; no automatic resume')
def guard():
 for x in load(R/'audit/input_lock.json'):
  if audit.sha(x['path'])!=x['sha256']:raise IntegrityError('Locked input changed: '+x['path'])
 import importlib.util
 p=R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
 spec=importlib.util.spec_from_file_location('b1_gpt_guard',p);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
 if g.collect()!=load(g.LOCK):raise IntegrityError('GPT frozen guard mismatch')

assert load(R/'validation/snapshot_store_v1/result.json')['status']=='PASS'
for x in load(R/'audit/preparation_registry_v2.json')['files']:assert audit.sha(R/x['path'])==x['sha256'],x['path']
guard();audit.verify();stopped()
S=R/'inputs/snapshot_v2';S.mkdir(parents=True,exist_ok=False)
jobs=load(R/'manifest300.json');census=load(R/'audit/source_census_v1.json');assert len(census)==251
protocol={'created_utc':now(),'n':251,'format':'SQLite content-addressed raw bytes + per-input JSON manifest','dedup':'only identical SHA256 and length; no path/repo/focal substitution','source_type':'historical pipeline-prepared source, not certified pristine Git','exclusions':'exact census exclusion list; target/build/tool metadata excluded, nested src paths retained','settings':'capture historical sandbox settings.xml separately when present; keep private','resume':'no automatic resume; partial evidence retained','min_free_bytes':12_000_000_000,'snapshot_code_sha256':audit.sha(__file__),'store_code_sha256':audit.sha(R/'src/snapshot_store_v1.py'),'manifest300_sha256':audit.sha(R/'manifest300.json'),'census_sha256':audit.sha(R/'audit/source_census_v1.json'),'fixture_sha256':audit.sha(R/'validation/snapshot_store_v1/result.json')}
protocol['reader_v2_sha256']=audit.sha(R/'src/snapshot_reader_v2.py')
protocol['explicit_continuation_record_sha256']=audit.sha(R/'audit/snapshot_continuation_v2.json')
protocol['prior_committed_roots']=7
dump(S/'protocol.json',protocol)
with (S/'content.sqlite3').open('xb'):pass
c=sqlite3.connect(S/'content.sqlite3')
with sqlite3.connect((R/'inputs/snapshot_v1/content.sqlite3').as_uri()+'?mode=ro',uri=True) as prior:prior.backup(c)
index=[];total=0;status(0,0);event('SNAPSHOT_V2_START',protocol_sha256=audit.sha(S/'protocol.json'),n=251)
try:
 for n,item in enumerate(census,1):
  stopped()
  if shutil.disk_usage(R).free<protocol['min_free_bytes']:raise IntegrityError('Disk floor reached; keep partial store')
  if n<=7:
   previous=load(R/'inputs/snapshot_v1/checkpoints'/f'{n:03d}.json');payload=load(R/previous['manifest'])
   assert audit.sha(R/previous['manifest'])==previous['sha256'] and payload['source_repo']==item['source_repo']
   path=S/'manifests'/f'{n:03d}.json';dump(path,payload)
   entry={**previous,'manifest':path.relative_to(R).as_posix(),'sha256':audit.sha(path),'reused_committed_snapshot_v1':True}
   index.append(entry);total+=entry['files'];dump(S/'checkpoints'/f'{n:03d}.json',entry);status(n,total);event('SNAPSHOT_REUSED_COMMITTED_INPUT',**entry);continue
  root=Path(item['source_repo']);expected={f['path'] for f in item['files']}
  actual,excluded=enumerate_census_paths(root)
  if actual!=expected or excluded!=set(item['excluded_output_or_tool_directories']):raise IntegrityError('Source inventory drift: '+str(item['class_indices']))
  descriptor_hashes={x['path']:x['sha256'] for x in item['build_descriptors']}
  rows=[];tick=time.monotonic();reader=SourceReader(root,c)
  for k,f in enumerate(item['files'],1):
   if k%100==1:stopped()
   rows.append(reader.capture(f['path'],f['bytes'],descriptor_hashes.get(f['path'])))
   if time.monotonic()-tick>=20:
    print(json.dumps({'phase':'snapshot_reading','root':n,'of':251,'files':k,'root_files':len(item['files']),'new_experiment_calls':0}),flush=True);tick=time.monotonic()
  keyrows=[j for j in jobs if j['sample_index_1based'] in item['class_indices']]
  for j in keyrows:
   focal=next(x for x in rows if x['relative']==j['focal_path'])
   if focal['sha256']!=j['source_candidate']['focal_sha256']:raise IntegrityError('Focal drift')
  reader.validate_directories()
  settings=root.parent.parent/'settings.xml'
  context=capture_file(c,settings.parent,settings.name) if settings.is_file() else None
  payload={'source_repo':str(root),'class_indices':item['class_indices'],'files':rows,'excluded':item['excluded_output_or_tool_directories'],'settings_source':str(settings) if context else None,'settings':context,'captured_utc':now()}
  c.commit();path=S/'manifests'/f'{n:03d}.json';dump(path,payload)
  entry={'snapshot_index':n,'class_indices':item['class_indices'],'manifest':path.relative_to(R).as_posix(),'sha256':audit.sha(path),'files':len(rows),'bytes':sum(x['bytes'] for x in rows)};index.append(entry);total+=len(rows)
  dump(S/'checkpoints'/f'{n:03d}.json',entry);status(n,total)
  event('SNAPSHOT_INPUT_COMPLETE',**entry)
  print(json.dumps({'snapshot_roots_complete':n,'n':251,'files_total':total,'new_experiment_calls':0}),flush=True)
 assert total==sum(x['file_count'] for x in census)
 assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 count,unique_bytes=c.execute('SELECT COUNT(*),SUM(nbytes) FROM blobs').fetchone()
 # Independently read all stored bytes once; no file hash is trusted merely because it is a key.
 for h,length,data in c.execute('SELECT sha256,nbytes,data FROM blobs'):
  stopped()
  if len(data)!=length or digest(data)!=h:raise IntegrityError('Stored blob verification failed')
 c.execute("INSERT INTO metadata VALUES ('complete','true')");c.commit();c.close();c=None
 dump(S/'index.json',index);guard();audit.verify()
 result={'status':'PASS','snapshots':len(index),'source_files':total,'logical_source_bytes':sum(x['bytes'] for x in index),'unique_blobs':count,'unique_bytes_including_settings':unique_bytes,'store_bytes':(S/'content.sqlite3').stat().st_size,'store_sha256':audit.sha(S/'content.sqlite3'),'index_sha256':audit.sha(S/'index.json'),'protocol_sha256':audit.sha(S/'protocol.json'),'every_blob_rehashed':True,'GPT_guard':'PASS','new_experiment_calls':0,'benchmark_admitted':False}
 dump(S/'complete.json',result);event('SNAPSHOT_COMPLETE',**result);print(json.dumps(result,indent=2),flush=True)
except BaseException as ex:
 if c is not None:c.rollback();c.close()
 dump(S/'interrupted.json',{'timestamp_utc':now(),'completed_roots':len(index),'error_type':type(ex).__name__,'detail':str(ex),'auto_resume':False})
 event('SNAPSHOT_INTERRUPTED',completed_roots=len(index),error_type=type(ex).__name__,detail=str(ex));raise

import json
from pathlib import Path
from snapshot_store_v1 import open_new_store,restore,IntegrityError
from snapshot_reader_v3 import capture_many
R=Path(__file__).resolve().parents[1];O=R/'validation/snapshot_reader_v3';O.mkdir(parents=True,exist_ok=False)
root=O/'source';root.mkdir();files=[]
for i in range(150):
 p=root/f'{i:03d}.txt';data=f'synthetic content {i%7}\r\n'.encode();p.write_bytes(data);files.append({'path':p.name,'bytes':len(data)})
c=open_new_store(O/'content.sqlite3');progress=[];rows=capture_many(root,c,files,{},lambda:None,lambda n,total:progress.append(n));c.commit();restore(c,rows,O/'restore')
assert c.execute('SELECT COUNT(*) FROM blobs').fetchone()[0]==7
assert [r['relative'] for r in rows]==[f['path'] for f in files]
assert all((root/r['relative']).read_bytes()==(O/'restore'/r['relative']).read_bytes() for r in rows)
assert progress==[64,128,150]
try:capture_many(root,c,files,{files[0]['path']:'0'*64},lambda:None,lambda *args:None)
except IntegrityError:pass
else:raise AssertionError('Hash mismatch not rejected')
def stop():raise IntegrityError('synthetic stop')
try:capture_many(root,c,files,{},stop,lambda *args:None)
except IntegrityError:pass
else:raise AssertionError('Stop not honored')
c.close();result={'status':'PASS','files_read_and_restored':150,'unique_blobs':7,'workers':8,'checks':['stable input order','exact restored bytes','dedup exact only','bounded64 futures','hash mismatch','stop before chunk'],'experimental_workers':0,'experiment_calls':0}
with (O/'result.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))

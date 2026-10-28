import json
from pathlib import Path
from snapshot_store_v1 import *
from snapshot_reader_v2 import SourceReader
R=Path(__file__).resolve().parents[1];O=R/'validation/snapshot_reader_v2';O.mkdir(parents=True,exist_ok=False)
root=O/'source';(root/'dir').mkdir(parents=True);(root/'dir/a').write_bytes(b'exact\r\n');(root/'b').write_bytes(b'exact\r\n')
c=open_new_store(O/'store.sqlite3');reader=SourceReader(root,c);rows=[reader.capture(x) for x in ['dir/a','b']];reader.validate_directories();c.commit();restore(c,rows,O/'restore')
assert c.execute('SELECT COUNT(*) FROM blobs').fetchone()[0]==1
assert (O/'restore/dir/a').read_bytes()==b'exact\r\n'
tests=['read_every_file_hash','dedup_equal_bytes','restore_exact','directory_identity_guard_initial']
def reject(name,fn):
 try:fn()
 except IntegrityError:tests.append(name)
 else:raise AssertionError(name)
reject('hash_drift',lambda:reader.capture('b',expected_sha='0'*64))
reject('size_drift',lambda:reader.capture('b',expected_size=0))
reject('escape',lambda:reader.capture('../escape'))
assert (root/'dir').resolve().is_relative_to(O.resolve()) and (root/'dir_old').resolve().is_relative_to(O.resolve())
(root/'dir').rename(root/'dir_old');(root/'dir').mkdir()
reject('directory_swapped',reader.validate_directories)
c.close();result={'status':'PASS','checks':tests,'experiment_calls':0}
with (O/'result.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))

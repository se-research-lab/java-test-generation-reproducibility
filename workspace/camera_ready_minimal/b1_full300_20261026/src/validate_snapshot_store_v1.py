"""Synthetic recovery/integrity checks, no Java/Gradle/GPT invocation."""
import json,sys
from pathlib import Path
from snapshot_store_v1 import *
R=Path(__file__).resolve().parents[1];out=R/'validation/snapshot_store_v1';out.mkdir(parents=True,exist_ok=False)
src=out/'source';(src/'src/main/java').mkdir(parents=True)
(src/'src/main/java/A.java').write_bytes(b'package fixture; class A {}\r\n')
(src/'copy.java').write_bytes((src/'src/main/java/A.java').read_bytes())
(src/'empty').write_bytes(b'')
c=open_new_store(out/'store.sqlite3');rows=[capture_file(c,src,p) for p in ['src/main/java/A.java','copy.java','empty']];c.commit()
assert c.execute('SELECT COUNT(*) FROM blobs').fetchone()[0]==2
restore(c,rows,out/'restored');assert (out/'restored/src/main/java/A.java').read_bytes()==(src/'copy.java').read_bytes()
tests=['deduplicate_equal_bytes','restore_exact_bytes']
def reject(name,fn):
 try:fn()
 except IntegrityError:tests.append(name)
 else:raise AssertionError('Expected rejection: '+name)
for i,p in enumerate(['../escape','/absolute','C:/escape','x\\y','file:stream','a/./b','a//b']):reject('invalid_path_'+str(i),lambda p=p:safe_relative(p))
reject('size_drift',lambda:capture_file(c,src,'copy.java',expected_size=999))
reject('hash_drift',lambda:capture_file(c,src,'copy.java',expected_sha='0'*64))
reject('restore_overwrite',lambda:restore(c,rows,out/'restored'))
reject('case_collision',lambda:restore(c,[rows[1],dict(rows[1],relative='COPY.java')],out/'collision'))
c.execute('UPDATE blobs SET data=? WHERE sha256=?',(b'corrupted',rows[0]['sha256']));c.commit()
reject('corrupt_blob',lambda:restore(c,rows,out/'corrupt_restore'));c.close()
result={'status':'PASS','checks':tests,'count':len(tests),'source_unchanged':(src/'copy.java').read_bytes()==b'package fixture; class A {}\r\n','experiment_calls':0}
with (out/'result.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))

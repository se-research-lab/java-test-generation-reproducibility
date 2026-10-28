"""Fix JSON serialization in new offline checker only; keep prior bytes and hashes."""
import sys,json,shutil,ast
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
H=B/'final_handoff_20261024';A=H/'artifact';backup=H/'internal_backups/artifact_before_serialization_fix';backup.mkdir()
for n in ['reproduce_analytics.py','MANIFEST.json','SHA256SUMS']:shutil.copy2(A/n,backup/n)
p=A/'reproduce_analytics.py';s=p.read_text();s=s.replace("sum(np.isfinite(number(r[a+'_'+k])) for r in rs)","sum(bool(np.isfinite(number(r[a+'_'+k]))) for r in rs)");assert s!=p.read_text();p.write_text(s,encoding='utf-8')
audit.log('FILE_REVISION',path=p.relative_to(B).as_posix(),before_sha256=audit.sha(backup/p.name),after_sha256=audit.sha(p),backup=(backup/p.name).relative_to(B).as_posix(),reason='Use Python bool for serializable denominator count; raw-score and bootstrap assertions already passed; no data change')
# Include recursive local Python imports used by archived E1 code, as source only.
done={p.name for p in (A/'code/E1').glob('*.py')};pending=list(done)
while pending:
 n=pending.pop();q=A/'code/E1'/n
 try:tree=ast.parse(q.read_text(encoding='utf-8-sig'))
 except SyntaxError:continue
 modules=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):modules += [x.name.split('.')[0] for x in node.names]
  elif isinstance(node,ast.ImportFrom) and node.module:modules.append(node.module.split('.')[0])
 for m in modules:
  name=m+'.py';src=B/'src'/name
  if name not in done and src.is_file():
   assert 'repeat' not in name;shutil.copy2(src,A/'code/E1'/name);done.add(name);pending.append(name)
entries=[{'path':q.relative_to(A).as_posix(),'bytes':q.stat().st_size,'sha256':audit.sha(q)} for q in sorted(A.rglob('*')) if q.is_file() and q.name not in ['MANIFEST.json','SHA256SUMS']]
(A/'MANIFEST.json').write_text(json.dumps({'scope':'accepted historical300 plus final E1_fixed49 only','files':entries},indent=2))
(A/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['path']+'\n' for x in entries)+audit.sha(A/'MANIFEST.json')+'  MANIFEST.json\n')
audit.log('ARTIFACT_MANIFEST_REFRESH',backup=backup.relative_to(B).as_posix(),new_manifest_sha256=audit.sha(A/'MANIFEST.json'),files=len(entries),experiment_calls=0)
print(json.dumps({'status':'OFFLINE_CHECKER_SERIALIZATION_FIXED','archived_E1_local_modules':len(done),'files':len(entries)}))

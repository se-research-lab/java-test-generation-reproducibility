"""Verify local source-bundle hashes. Standard library only; no runner imports."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'manifests/FILE_MANIFEST.json').read_text(encoding='utf-8'))
bad=[]
for row in manifest:
    p=root/row['path']
    if not p.is_file():bad.append({'path':row['path'],'problem':'missing'});continue
    if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:bad.append({'path':row['path'],'problem':'hash mismatch'})
print(json.dumps({'status':'FAIL' if bad else 'PASS','files_checked':len(manifest),'problems':bad,'experimental_code_imported':False,'downloads':0,'new_experiments':0},indent=2))
sys.exit(bool(bad))

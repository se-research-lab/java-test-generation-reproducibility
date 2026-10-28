import json,shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v2_15pages';p=REV/'source/sections/06_threats.tex'
text=p.read_text(encoding='utf-8');old='Temperature zero is not deterministic';new='Temperature zero does not guarantee deterministic output'
assert text.count(old)==1
backup=REV/'backup_editorial_precision01/06_threats.tex';backup.parent.mkdir(exist_ok=False);before=audit.sha(p);shutil.copy2(p,backup);assert audit.sha(backup)==before
p.write_text(text.replace(old,new),encoding='utf-8')
audit.log('FILE_REVISION',path=p.relative_to(BASE).as_posix(),before_sha256=before,after_sha256=audit.sha(p),backup=backup.relative_to(BASE).as_posix(),reason='Restore qualified nondeterminism wording from original revision; no numeric/design change')
print(json.dumps({'status':'PASS','only_wording_change':True}))

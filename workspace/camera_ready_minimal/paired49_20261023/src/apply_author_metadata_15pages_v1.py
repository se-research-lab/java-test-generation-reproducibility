"""Insert user-provided authors, preserving order and conference class/layout."""
import json,shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v2_15pages';SRC=REV/'source';backup=REV/'backup_author_metadata01';backup.mkdir(exist_ok=False)
changes={}
p=SRC/'main.tex';text=p.read_text(encoding='utf-8')
old='\\author{Anonymous Author(s)}\n\\authorrunning{Anonymous Author(s)}\n\\institute{Affiliation withheld for double-blind review}'
new=r'''\author{Truong Dan Huy \and Vuong Quoc Khanh \and Tran Minh Quy \and
Le Tran Anh Khoa \and Tran Bich Tram}
\authorrunning{Truong Dan Huy et al.}
\institute{FPT University\\
\email{truongdanhuyak@gmail.com, khanhvuong200599@gmail.com}\\
\email{tranminhquy090@gmail.com, anhkhoa24092005@gmail.com}\\
\email{tranbichtram252@icloud.com}}'''
assert text.count(old)==1;changes[p]=text.replace(old,new)
p=SRC/'sections/08_disclosure.tex';text=p.read_text(encoding='utf-8')
old='The replication package, containing paper sources, scripts, dataset handoff notes, run and generated-test manifests, logs, and derived result tables, is available at [replication package withheld for double-blind review; submitted as supplementary material]; credentials and local cache contents are excluded.'
new='Replication materials comprise paper sources, scripts, dataset handoff notes, run and generated-test manifests, logs, and derived result tables; credentials and local cache contents are excluded. Access information will accompany the final camera-ready submission.'
assert text.count(old)==1;changes[p]=text.replace(old,new)
records=[]
for p,newtext in changes.items():
    rel=p.relative_to(SRC);dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    before=audit.sha(p);shutil.copy2(p,dest);assert audit.sha(dest)==before
    p.write_text(newtext,encoding='utf-8');after=audit.sha(p)
    row={'path':p.relative_to(BASE).as_posix(),'before_sha256':before,'after_sha256':after,'backup':dest.relative_to(BASE).as_posix(),'reason':'User-provided author order, affiliation/emails; artifact URL pending, remove double-blind placeholder'}
    audit.log('FILE_REVISION',**row);records.append(row)
metadata={'authors_in_order':[{'name':'Truong Dan Huy','email':'truongdanhuyak@gmail.com'},{'name':'Vuong Quoc Khanh','email':'khanhvuong200599@gmail.com'},{'name':'Tran Minh Quy','email':'tranminhquy090@gmail.com'},{'name':'Le Tran Anh Khoa','email':'anhkhoa24092005@gmail.com'},{'name':'Tran Bich Tram','email':'tranbichtram252@icloud.com'}],'affiliation':'FPT University','corresponding_author':'awaiting user clarification','artifact_URL':'not finalized by user','funding_COI_confirmation':'awaiting user reply','page_limit_total_including_references':15,'changes':records}
with (REV/'author_metadata_v1.json').open('x',encoding='utf-8') as f:json.dump(metadata,f,ensure_ascii=False,indent=2);f.write('\n')
audit.log('MANUSCRIPT_V2_AUTHOR_METADATA_APPLIED',manifest_sha256=audit.sha(REV/'author_metadata_v1.json'),names_and_emails_from_user=True,page_limit_from_user=15,artifact_URL_invented=False)
print(json.dumps({'status':'APPLIED','authors':5,'affiliation':'FPT University','artifact_URL':'pending','corresponding_author':'pending','old_manuscript_or_experiments_edited':False},ensure_ascii=False,indent=2))

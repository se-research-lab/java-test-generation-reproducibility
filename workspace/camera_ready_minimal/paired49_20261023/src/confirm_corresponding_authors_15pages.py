import json,shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v2_15pages';p=REV/'source/main.tex';text=p.read_text(encoding='utf-8')
old=r'''\author{Truong Dan Huy \and Vuong Quoc Khanh \and Tran Minh Quy \and
Le Tran Anh Khoa \and Tran Bich Tram}'''
new=r'''\author{Truong Dan Huy \and Vuong Quoc Khanh \and Tran Minh Quy \and
Le Tran Anh Khoa \and Tran Bich Tram \and Le Thi Quynh Chi}'''
assert text.count(old)==1;text=text.replace(old,new)
old=r'''\email{tranbichtram252@icloud.com}}'''
new=r'''\email{tranbichtram252@icloud.com, chiltq6@fe.edu.vn}\\
Corresponding authors: Truong Dan Huy and Le Thi Quynh Chi}'''
assert text.count(old)==1;text=text.replace(old,new)
backup=REV/'backup_corresponding_metadata02/main.tex';backup.parent.mkdir(exist_ok=False);before=audit.sha(p);shutil.copy2(p,backup);assert audit.sha(backup)==before
p.write_text(text,encoding='utf-8');audit.log('FILE_REVISION',path=p.relative_to(BASE).as_posix(),before_sha256=before,after_sha256=audit.sha(p),backup=backup.relative_to(BASE).as_posix(),reason='User added Le Thi Quynh Chi as sixth author and confirmed two corresponding authors')
previous=json.loads((REV/'author_metadata_v1.json').read_text(encoding='utf-8'));previous['authors_in_order'].append({'name':'Le Thi Quynh Chi','email':'chiltq6@fe.edu.vn'});previous['corresponding_authors']=[{'name':'Truong Dan Huy','email':'truongdanhuyak@gmail.com'},{'name':'Le Thi Quynh Chi','email':'chiltq6@fe.edu.vn'}];previous.pop('corresponding_author',None);previous['funding_COI_confirmation']='User explicitly confirms no funding and no conflicts of interest';previous['funding']='none';previous['conflicts_of_interest']='none';previous['author_order_note']='Original five in supplied order, newly supplied lecturer appended sixth; no reordering';previous['artifact_URL']='not finalized by user'
with (REV/'author_metadata_v2.json').open('x',encoding='utf-8') as f:json.dump(previous,f,ensure_ascii=False,indent=2);f.write('\n')
audit.log('MANUSCRIPT_V2_CORRESPONDING_AUTHORS_CONFIRMED',metadata_sha256=audit.sha(REV/'author_metadata_v2.json'),authors=6,corresponding_authors=['Truong Dan Huy','Le Thi Quynh Chi'],funding='none user confirmed',COI='none user confirmed',artifact_URL='pending')
print(json.dumps({'authors':6,'corresponding_authors':['Truong Dan Huy','Le Thi Quynh Chi'],'funding_COI':'none confirmed','artifact_URL':'pending'}))

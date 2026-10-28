"""Seal and package the user-requested disclosure-only manuscript copy."""
import hashlib,json,re,subprocess,sys,unicodedata,zipfile
from datetime import datetime,timezone
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
R=B/'manuscript_revision_v5_disclosure';OLD=B/'manuscript_revision_v4_submission';S=R/'source';D=R/'build_01';O=R/'output';V=B/'validation/disclosure_only_release_v1';sha=audit.sha
rel=lambda p:Path(p).relative_to(B).as_posix()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def register(p):audit.log('NEW_FILE_REGISTERED',path=rel(p),sha256=sha(p),bytes=p.stat().st_size,change_type='new isolated disclosure-only release output')
def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
    register(p)
def text(p,t):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(t)
    register(p)
assert not O.exists() and not V.exists();register(Path(__file__))
closed=read(B/'audit/camera_ready_response_registry_v1.json')
for row in closed['files']:assert sha(B/row['path'])==row['sha256'],row['path']
copy=read(R/'source_copy_manifest.json')['files'];summary=read(D/'build_summary.json');actual={n:sha(S/n) for n in copy}
assert actual==summary['input_hashes'];assert [n for n in copy if copy[n]!=actual[n]]==['sections/08_disclosure.tex']
assert sha(R/'backups/disclosure_removal_v1/sections/08_disclosure.tex')==copy['sections/08_disclosure.tex']
doc=fitz.open(D/'main.pdf');assert len(doc)==15
allpdf=unicodedata.normalize('NFKC',' '.join(p.get_text() for p in doc));allpdf=' '.join(allpdf.split())
assert 'AI assistant' not in allpdf and 'OpenAI Codex' not in allpdf
assert 'no external funding' in allpdf and 'no conflicts of interest' in allpdf and 'Corresponding author: Le Thi Quynh Chi' in allpdf
render=read(D/'rendered/render_manifest.json');assert render['pages_changed_vs_verified_v4']==[14,15]
for n,h in render['PNG_hashes'].items():
    assert sha(D/'rendered'/n)==h
    if n not in ['page_14.png','page_15.png']:assert sha(OLD/'build_01/rendered'/n)==h
V.mkdir()
qa={'status':'PASS','pages':15,'PDF_sha256':sha(D/'main.pdf'),'new_fullsize_visual_review_pages':[14,15],'other13_PNGs_byte_identical_to_verified_v4':True,'clipping_overlap_or_missing_glyphs':False,'reviewer':'root agent full-size rendered page inspection','references_pages':[14,15]}
dump(V/'visual_QA.json',qa)
guard=B.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
g=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],cwd=B,capture_output=True,text=True,encoding='utf-8');assert g.returncode==0,(g.stdout,g.stderr);gj=json.loads(g.stdout);assert gj['status']=='PASS';text(V/'GPT_frozen_guard.txt',g.stdout)
audit.verify()
dump(V/'final_validation.json',{'status':'PASS','timestamp_utc':datetime.now(timezone.utc).isoformat(),'pages':15,'only_changed_source':'sections/08_disclosure.tex','other14_source_inputs_byte_identical_to_v4':True,'scientific_data_and_results_unchanged':True,'AI_acknowledgement_omitted_as_requested':True,'funding_conflicts_and_corresponding_author_retained':True,'visual_QA':'PASS','old_registry_files_verified':len(closed['files']),'GPT_frozen_guard':gj,'original_backup_pairs_verified':585,'source_hashes':actual,'PDF_sha256':sha(D/'main.pdf'),'new_experiment_or_API_calls':0,'publisher_AI_disclosure_compliance_not_certified':True,'no_copy_editing_only_claim_added':True,'previous_failed_postbuild_textcheck_retained_in_audit':True})
O.mkdir();pdf=O/'pdf/FISAT2026_camera_ready_review_draft.pdf';pdf.parent.mkdir()
with pdf.open('xb') as f:f.write((D/'main.pdf').read_bytes())
assert sha(pdf)==sha(D/'main.pdf');register(pdf)
text(O/'README.md','''# FISAT2026 manuscript review draft\n\nContains main.pdf and its15 source inputs;15 pages including references. Corresponding author: Le Thi Quynh Chi (chiltq6@fe.edu.vn).\n\nRebuild using Tectonic0.17.0:\n\n    tectonic --untrusted --keep-logs main.tex\n\nA populated cache permits --only-cached. Scientific observations and research questions are unchanged from the preceding verified revision. Replication-artifact access information remains to be finalized. This archive is a manuscript review package and has not been submitted.\n''')
dump(O/'source_manifest.json',{'files':actual,'PDF_member':'main.pdf','PDF_sha256':sha(pdf),'pages':15})
archive=O/'FISAT2026_upload_review_draft.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    z.write(pdf,'main.pdf')
    for n in sorted(actual):z.write(S/n,n)
    for n in ['README.md','source_manifest.json']:z.write(O/n,n)
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==18 and z.testzip() is None
    assert hashlib.sha256(z.read('main.pdf')).hexdigest()==sha(pdf)
    for n,h in actual.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
register(archive)
text(R/'CHANGE_NOTE.md','''# Thay đổi theo yêu cầu tác giả\n\nBản v5 chỉ bỏ đoạn ghi nhận hỗ trợ AI trong08_disclosure.tex; giữ khai báo không tài trợ, không xung đột lợi ích và corresponding author Le Thi Quynh Chi.14 nguồn còn lại giữ byte nguyên, PDF vẫn15 trang. Bản v4 và toàn bộ audit/backups giữ nguyên. Không thêm tuyên bố rằng AI chỉ được dùng để copy-editing.\n\nBản này thay PDF/ZIP v4 để review nội dung hiện tại; thư giải trình reviewer về số liệu không đổi. Ghi chú nội bộ: việc bỏ đoạn khai báo theo yêu cầu tác giả không được dùng để chứng nhận đã đáp ứng chính sách AI của hội nghị. Nguồn đối chiếu: https://fisat.eai-conferences.org/2026/camera-ready-instructions/. Chưa upload hoặc nộp.\n''')
dump(O/'release_manifest.json',{'status':'VERIFIED_DISCLOSURE_EDIT_REVIEW_DRAFT','PDF':{'path':rel(pdf),'sha256':sha(pdf),'pages':15},'upload_archive':{'path':rel(archive),'sha256':sha(archive),'members':18,'exact_PDF_and_source_match':True},'change':'Omit AI-use acknowledgement per explicit user request; retain funding/conflicts','corresponding_author':'Le Thi Quynh Chi','verification':{rel(p):sha(p) for p in [V/'visual_QA.json',V/'final_validation.json',V/'GPT_frozen_guard.txt']},'publisher_AI_disclosure_compliance_not_certified':True,'submission_performed':False})
entries=set()
for d in [S,R/'backups',D,O,V]:entries.update(p for p in d.rglob('*') if p.is_file())
entries.update([R/'source_copy_manifest.json',R/'change_manifest.json',R/'tectonic_cache_copy_manifest.json',R/'CHANGE_NOTE.md',B/'src/prepare_v5_disclosure_removal_v1.py',B/'src/render_v5_disclosure_check_v1.py',Path(__file__),B/'audit/camera_ready_response_registry_v1.json'])
rows=[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(entries)]
reg=B/'audit/disclosure_only_registry_v1.json';dump(reg,{'status':'CLOSED','files':rows,'prior_registry_sha256':sha(B/'audit/camera_ready_response_registry_v1.json'),'original_files_unchanged':True,'new_experiment_API_calls':0})
for row in rows:assert sha(B/row['path'])==row['sha256'],row['path']
audit.verify()
print(json.dumps({'status':'PASS','pages':15,'registry_files':len(rows),'PDF':str(pdf),'archive':str(archive),'all_scientific_sources_unchanged':True,'submission_performed':False},indent=2))

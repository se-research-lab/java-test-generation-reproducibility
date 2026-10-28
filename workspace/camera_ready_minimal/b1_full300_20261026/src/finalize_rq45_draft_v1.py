"""Verify and package reviewed manuscript and offline evidence; never submit."""
import json,sys,shutil,zipfile,hashlib,subprocess,os,re,difflib
from decimal import Decimal
from datetime import datetime,timezone
from pathlib import Path
import fitz
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';ROOT=R.parents[1];O=R/'analysis_camera_ready_rq45_v1';S=O/'manuscript';BUILD=O/'build_04';D=O/'delivery'
sys.path.insert(0,str(B));import audit
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,d):
 with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
assert not D.exists();D.mkdir()
analysis=read(O/'analysis.json');rows=read(O/'class_evidence300.json');known=[r for r in rows if r['E1_build'] is not None]
assert sum(r['E1_build'] for r in known)==204 and len(known)==270
gap=sum(Decimal(str(r['G0_strict']))-Decimal(str(r['E1_strict'])) for r in known)/Decimal(270)
assert abs(float(gap)-analysis['cohorts']['E1_observed270']['mean_difference_pp'])<1e-10
assert sum(r['G0_build'] for r in rows)==61
for p,h in read(O/'input_hashes.json').items():assert audit.sha(p)==h,p
old=B/'final_handoff_20261025_private/manuscript';original=read(O/'source_change_manifest.json')['backup_hashes']
for rel,h in original.items():assert audit.sha(old/rel)==h==audit.sha(O/'backup/manuscript'/rel)
newhash={rel:audit.sha(S/rel) for rel in original}
assert newhash==read(BUILD/'build_summary.json')['source_hashes']
for name in ('main.tex','llncs.cls','splncs04.bst','references.bib','references.tex','sections/08_disclosure.tex'):
 assert newhash[name]==original[name]
def rqitems(p):return re.findall(r'\\item \\textbf\{RQ[1-5].*',p.read_text(encoding='utf-8'))
assert rqitems(S/'sections/01_introduction.tex')==rqitems(old/'sections/01_introduction.tex')
def rqrows(p):return re.findall(r'^RQ[1-3] & .*$',p.read_text(encoding='utf-8'),re.M)
assert rqrows(S/'sections/04_results.tex')==rqrows(old/'sections/04_results.tex')
guard=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py')],capture_output=True,text=True,encoding='utf-8');assert guard.returncode==0
g= json.loads(guard.stdout);assert g['status']=='PASS';dump(D/'GPT_frozen_guard.json',g)
doc=fitz.open(BUILD/'main.pdf');assert len(doc)==15
text=' '.join(' '.join(p.get_text() for p in doc).split());assert '??' not in text
assert 'Corresponding author: Le Thi Quynh Chi' in text
for person in ('Truong Dan Huy','Vuong Quoc Khanh','Tran Minh Quy','Le Tran Anh Khoa','Tran Bich Tram','Le Thi Quynh Chi'):assert person in text
assert 'replication package withheld for double-blind review; submitted as supplementary material' in text
log=(BUILD/'main.log').read_text(encoding='utf-8');assert 'Overfull' not in log and 'undefined references' not in log
render=read(BUILD/'rendered/render_comparison.json');assert render['changed_vs_build03']==['page-12.png']
qa={'status':'PASS','pages':15,'visual_review':'All15 build03 pages inspected; build04 page12 re-inspected; other14 PNGs byte-identical','no_visible_clipping_overlap_missing_glyphs':True,'overfull_boxes':0,'references_start_page':13,'PDF_sha256':audit.sha(BUILD/'main.pdf')}
dump(D/'visual_QA.json',qa)
pdf=D/'FISAT2026_RQ45_evidence_revision.pdf';shutil.copy2(BUILD/'main.pdf',pdf)
readme='''# Separate RQ4/RQ5 evidence revision

15 pages including references; six authors, Le Thi Quynh Chi sole corresponding author.
This is a review draft, not a claim of complete empirical resolution or submission.
The PDF and source in this ZIP match exactly. Experimental code/data, caches and credentials are excluded.
E0 is the historical assertion-disabled comparison; E1 has270 raw outcomes and30 unscored slots.
No new GPT/EvoSuite/Gradle experiment was run for this revision. Original GPT cohorts61/45/300 remain frozen.

Build from the extracted source directory with Tectonic0.17.0:

    tectonic --untrusted --keep-logs main.tex

With a populated dependency cache, add --only-cached. A clean-output rebuild was checked locally.
The build uses references.tex; references.bib, llncs.cls and splncs04.bst are included.
Private supplementary-only wording is retained. No public artifact URL or release is promised.
'''
(D/'README.md').write_text(readme,encoding='utf-8')
dump(D/'source_manifest.json',{'source_hashes':newhash,'PDF_sha256':audit.sha(pdf),'pages':15})
zpath=D/'FISAT2026_RQ45_manuscript_source.zip'
with zipfile.ZipFile(zpath,'x',zipfile.ZIP_DEFLATED) as z:
 z.write(pdf,'main.pdf')
 for rel in sorted(newhash):z.write(S/rel,rel)
 for n in ('README.md','source_manifest.json'):z.write(D/n,n)
with zipfile.ZipFile(zpath) as z:
 assert z.testzip() is None and hashlib.sha256(z.read('main.pdf')).hexdigest()==audit.sha(pdf)
 assert set(z.namelist())==set(newhash)|{'main.pdf','README.md','source_manifest.json'}
 for rel,h in newhash.items():assert hashlib.sha256(z.read(rel)).hexdigest()==h
 extracted=O/'validation/zip_rebuild/source';extracted.mkdir(parents=True)
 for rel in newhash:
  p=extracted/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(rel))
build=extracted.parent/'clean_build';build.mkdir()
env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(O/'tectonic_cache')
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
proc=subprocess.run([str(tool),'--only-cached','--untrusted','--keep-logs','--outdir',str(build),str(extracted/'main.tex')],cwd=extracted,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(build/'stdout.txt').write_text(proc.stdout,encoding='utf-8');(build/'stderr.txt').write_text(proc.stderr,encoding='utf-8');assert proc.returncode==0
rebuilt=fitz.open(build/'main.pdf');assert len(rebuilt)==15
assert [p.get_text() for p in rebuilt]==[p.get_text() for p in doc]
assert all(rebuilt[i].get_pixmap().samples==doc[i].get_pixmap().samples for i in range(15))
for n in ('RESPONSE_TO_REVIEWERS.md','REVIEWER_STATUS.json','BAO_CAO_LOI_VA_DIEU_CHINH_RQ45.md'):shutil.copy2(O/n,D/n)
check='''# Checklist nộp Confy+ — bản RQ4/RQ5 riêng

- [x] PDF15trang gồm references; render15trang đã kiểm.
- [x] ZIP chứa đúng PDF và đầy đủ15source inputs; không có code thực nghiệm/secrets.
- [x] Extract ZIP, build ra thư mục sạch;15trang và pixel render trùng PDF giao.
- [x] Sáu tác giả; Le Thi Quynh Chi corresponding duy nhất; không tài trợ/xung đột lợi ích theo tác giả cung cấp.
- [x] Giữ năm RQ, GPT61/45/300, original raw; E0/E1 và denominators tách rõ.
- [x] Không đưa repeated dang dở; không claim E1 NI/full300 verified; không public code/URL.
- [ ] Tác giả rà và chấp nhận interpretation RQ4–RQ5 mới, policy-selection caveat và các trạng thái partial/open trong response.
- [ ] Tác giả kiểm thông tin trên Confy+, tư cách tác giả và receipt supplementary tương ứng câu availability.
- [ ] Tác giả kiểm yêu cầu khai báo AI theo hướng dẫn hội nghị; bản này không thêm đoạn AI-use theo yêu cầu, không chứng nhận công việc chỉ là copy-editing.
- [ ] Tác giả xác nhận registration/license và thực hiện upload; agent chưa upload, thanh toán hoặc ký.

Hướng dẫn: https://fisat.eai-conferences.org/2026/camera-ready-instructions/
Trang yêu cầu PDF riêng và archive chứa PDF+source theo Authors' Kit. Giới hạn15trang theo tác giả/reviewer.
R2.1, margin practical justification, repeated variance, equal compute và hybrid vẫn chưa được đánh dấu fully resolved.
'''
(D/'CHECKLIST_CONFY.md').write_text(check,encoding='utf-8')
diff=''.join(''.join(difflib.unified_diff((old/rel).read_text(encoding='utf-8').splitlines(True),(S/rel).read_text(encoding='utf-8').splitlines(True),fromfile='original/'+rel,tofile='revision/'+rel)) for rel in original if original[rel]!=newhash[rel])
(O/'final_manuscript_changes.diff').write_text(diff,encoding='utf-8')
validation={'status':'VERIFIED_REVIEW_DRAFT_NOT_SUBMITTED','timestamp_utc':datetime.now(timezone.utc).isoformat(),
 'original_source_hashes':original,'final_source_hashes':newhash,'five_RQs_exactly_preserved':True,'RQ123_table_rows_exactly_preserved':True,
 'GPT_guard':g,'independent_decimal_mean_gap':str(gap),'analysis_inputs_hash_verified':len(read(O/'input_hashes.json')),
 'pages':15,'visual_QA':qa,'source_zip_clean_rebuild':'PASS_15_PAGES_TEXT_AND_PIXELS_IDENTICAL',
 'PDF_sha256':audit.sha(pdf),'ZIP_sha256':audit.sha(zpath),'new_experiment_calls':0,'full300_E1_empirically_resolved':False,'submission_performed':False}
dump(D/'validation.json',validation)
audit.verify();audit.verify_chain()
hashes={p.name:audit.sha(p) for p in D.iterdir() if p.is_file()};dump(D/'DELIVERY_MANIFEST.json',hashes)
(D/'SHA256SUMS.txt').write_text('\n'.join(h+'  '+n for n,h in hashes.items())+'\n',encoding='utf-8')
audit.log('B1_RQ45_EVIDENCE_DRAFT_DELIVERED',manifest_sha256=audit.sha(D/'DELIVERY_MANIFEST.json'),PDF_sha256=audit.sha(pdf),ZIP_sha256=audit.sha(zpath),pages=15,original_modified=False,experiment_calls=0,submitted=False)
print(json.dumps({'PDF':str(pdf),'ZIP':str(zpath),'report':str(D/'BAO_CAO_LOI_VA_DIEU_CHINH_RQ45.md'),'pages':15,'zip_clean_rebuild':'PASS','GPT_guard':'PASS'},indent=2))

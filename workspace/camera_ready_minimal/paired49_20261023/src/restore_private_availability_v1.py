"""Author-requested availability wording only. No experimental imports or execution."""
import json,sys,shutil,subprocess,os,re,difflib
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
OLD=B/'final_handoff_20261024';R=B/'final_handoff_20261025_private';S=R/'manuscript';V=R/'validation'
assert not R.exists()
previous=json.loads((OLD/'RELEASE_MANIFEST.json').read_text())
for row in previous['files']:assert audit.sha(OLD/row['path'])==row['sha256'],row['path']
V.mkdir(parents=True);S.mkdir()
sources=[p for p in (OLD/'manuscript').rglob('*') if p.is_file() and p.suffix in ['.tex','.bib','.cls','.bst']]
assert len(sources)==15
for p in sources:
 rel=p.relative_to(OLD/'manuscript');q=S/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
backup=R/'backup/08_disclosure.tex';backup.parent.mkdir();shutil.copy2(S/'sections/08_disclosure.tex',backup)
p=S/'sections/08_disclosure.tex';before=p.read_text(encoding='utf-8')
old='Replication materials comprise paper sources, scripts, dataset handoff notes, run and generated-test manifests, logs, and derived result tables; credentials and local cache contents are excluded. Public artifact access has not yet been finalized.'
new='The replication package, containing paper sources, scripts, dataset handoff notes, run and generated-test manifests, logs, and derived result tables, is available at [replication package withheld for double-blind review; submitted as supplementary material]; credentials and local cache contents are excluded.'
assert before.count(old)==1;p.write_text(before.replace(old,new),encoding='utf-8')
(R/'backup/availability.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),p.read_text().splitlines(True),fromfile='previous/08_disclosure.tex',tofile='private/08_disclosure.tex')),encoding='utf-8')
audit.log('FILE_REVISION',path=p.relative_to(B).as_posix(),before_sha256=audit.sha(backup),after_sha256=audit.sha(p),backup=backup.relative_to(B).as_posix(),reason='Explicit author request: restore submitted supplementary-only availability phrase; do not publish experimental code')
changes=[p.relative_to(S).as_posix() for p in S.rglob('*') if p.is_file() and audit.sha(p)!=audit.sha(OLD/'manuscript'/p.relative_to(S))];assert changes==['sections/08_disclosure.tex']
response=(OLD/'RESPONSE_TO_REVIEWERS.md').read_text(encoding='utf-8')
response=response.replace('Replication-artifact access information must still be finalized before submission.','The original supplementary-only availability wording is retained: "replication package withheld for double-blind review; submitted as supplementary material". No public code release or artifact URL is promised.')
(R/'RESPONSE_TO_REVIEWERS.md').write_text(response,encoding='utf-8')
check=(OLD/'CHECKLIST_CONFY.md').read_text(encoding='utf-8')
check=check.replace('Thư mục mang ngày 20261024 vì bắt đầu đóng gói ngày đó.','Bản này cập nhật lựa chọn giữ kín code theo yêu cầu tác giả.')
check=check.replace('- `FISAT2026_experiment_artifact.zip`: gói thực nghiệm riêng, README, dependencies, configs/seeds, dữ liệu được nghiệm thu, bằng chứng raw và hashes. Không phải ZIP source manuscript.','- Artifact code thực nghiệm được giữ nội bộ ở bản bàn giao trước; không nằm trong ZIP manuscript mới và không được công khai. Không có URL/DOI public cần tạo theo lựa chọn hiện tại.')
check=check.replace('- [ ] Chốt public artifact URL/DOI, quyền phân phối và license cho artifact. Paper hiện nói trung thực chưa chốt public access. Khi có URL, cập nhật bản source riêng rồi build/render/đóng gói/hash lại; không chỉ sửa PDF.','- [ ] Đối chiếu supplementary đã nộp với hồ sơ Confy+/acceptance email. Paper giữ nguyên câu gốc: “replication package withheld for double-blind review; submitted as supplementary material”. Việc giữ câu theo yêu cầu tác giả không phải xác nhận độc lập rằng hệ thống đã nhận supplementary. Không công khai code, không tạo public URL/DOI và không tự upload thêm artifact.')
check=check.replace('Chỉ gửi artifact/response tại vị trí ban tổ chức yêu cầu hoặc đồng ý; không tự coi experiment ZIP là manuscript ZIP.','Response nộp theo yêu cầu ban tổ chức. Code thực nghiệm không đưa vào ZIP manuscript; bất kỳ việc gửi bổ sung code nào cần chỉ dẫn riêng của tác giả.')
check=check.replace('`../repeated_subset_v1/`','`../repeated_subset_v1/`')
(R/'CHECKLIST_CONFY.md').write_text(check,encoding='utf-8')
readme='''# Private supplementary availability revision

Author request: retain exactly "replication package withheld for double-blind review; submitted as supplementary material" from the submitted paper. No public code release, public artifact URL or DOI is promised. Experimental code/data remain local and are not included in this manuscript ZIP. No upload has been performed; actual supplementary receipt must be checked by the authors.

This manuscript remains 15 pages including references, with the same six authors and Le Thi Quynh Chi as sole corresponding author. All scientific sources except the availability paragraph are byte-identical to the preceding verified manuscript. No repeated-run data were added. No GPT/EvoSuite/E300/Maven/Gradle job was run.

Build from this directory using Tectonic 0.17.0:

    tectonic --untrusted --keep-logs main.tex

With an existing dependency cache, add --only-cached. The source includes all 15 manuscript inputs; no external images are needed. references.tex is the bibliography used by main.tex; references.bib and the Springer class/style are also included. README and manifest are packaging aids, not experimental code.
'''
(S/'README.md').write_text(readme,encoding='utf-8')
D=V/'build';D.mkdir();env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(B/'manuscript_revision_v6_final/tectonic_cache')
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--outdir',str(D),str(S/'main.tex')]
r=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(D/'stdout.txt').write_text(r.stdout);(D/'stderr.txt').write_text(r.stderr);assert r.returncode==0,r.stderr
doc=fitz.open(D/'main.pdf');assert len(doc)==15
whole=' '.join(' '.join(p.get_text().split()) for p in doc)
assert 'replication package withheld for double-blind review; submitted as supplementary material' in whole
assert 'Public artifact access has not yet been finalized' not in whole
assert 'Corresponding author: Le Thi Quynh Chi' in whole
log=(D/'main.log').read_text(errors='replace');bad=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)];assert not bad,bad
render=D/'rendered';render.mkdir();changed=[]
for i,page in enumerate(doc):
 out=render/f'page_{i+1:02}.png';page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(out)
 if audit.sha(out)!=audit.sha(OLD/'validation/clean_build/rendered'/out.name):changed.append(i+1)
shutil.copy2(D/'main.pdf',R/'FISAT2026_camera_ready_private.pdf');shutil.copy2(D/'main.pdf',S/'main.pdf')
report={'status':'BUILT_PENDING_VISUAL_QA','pages':15,'changed_sources':changes,'other14_manuscript_sources_byte_identical':True,'changed_render_pages':changed,'PDF_sha256':audit.sha(D/'main.pdf'),'original_statement_restored':True,'public_code_release_authorized':False,'experimental_code_in_manuscript_zip':False,'actual_supplementary_submission_independently_verified':False,'experiment_calls':0}
(V/'build_report.json').write_text(json.dumps(report,indent=2));audit.log('PRIVATE_AVAILABILITY_BUILD',report=report)
print(json.dumps(report,indent=2))
